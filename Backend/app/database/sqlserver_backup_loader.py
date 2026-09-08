import os
import re
import time
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import text

from app.database.database_manager import database_manager


MAX_BACKUP_SIZE_BYTES = 2 * 1024 * 1024 * 1024

BACKUP_TYPE_LABELS = {
    1: "FULL / Database",
    2: "Transaction Log",
    4: "File",
    5: "Differential Database",
    6: "Differential File",
    7: "Partial",
    8: "Differential Partial",
}


def _safe_db_name(filename: str) -> str:
    stem = Path(filename).stem
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_") or "uploaded"
    normalized = normalized[:48]
    return f"upload_{normalized}_{uuid.uuid4().hex[:8]}"


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _quote_identifier(value: str) -> str:
    return "[" + value.replace("]", "]]" ) + "]"


def _get_restore_directory(connection) -> Path:
    configured = os.getenv("DB_RESTORE_DIR")
    candidates: list[Path] = []

    if configured:
        candidates.append(Path(configured).expanduser())

    if os.name == "nt":
        candidates.append(Path(r"C:\SQLBackups"))

    row = connection.execute(
        text("SELECT CAST(SERVERPROPERTY('InstanceDefaultBackupPath') AS NVARCHAR(4000)) AS backup_path")
    ).mappings().first()
    backup_path = row["backup_path"] if row else None
    if backup_path:
        candidates.append(Path(backup_path))

    errors: list[str] = []
    for candidate in candidates:
        try:
            path = candidate.resolve()
            path.mkdir(parents=True, exist_ok=True)
            probe = path / f".kenneth_write_test_{uuid.uuid4().hex[:8]}"
            probe.write_bytes(b"ok")
            probe.unlink(missing_ok=True)
            return path
        except OSError as exc:
            errors.append(f"{candidate}: {exc}")

    raise RuntimeError(
        "No se encontró una carpeta donde el backend pueda guardar el .bak. "
        "Define DB_RESTORE_DIR en el .env (por ejemplo C:\\SQLBackups) y asegúrate "
        "de que FastAPI pueda escribir y SQL Server pueda leer esa carpeta. "
        f"Intentos: {' | '.join(errors)}"
    )


def _get_data_directories(connection) -> tuple[Path, Path]:
    row = connection.execute(
        text(
            """
            SELECT
                CAST(SERVERPROPERTY('InstanceDefaultDataPath') AS NVARCHAR(4000)) AS data_path,
                CAST(SERVERPROPERTY('InstanceDefaultLogPath') AS NVARCHAR(4000)) AS log_path
            """
        )
    ).mappings().first()

    data_path = row["data_path"] if row else None
    log_path = row["log_path"] if row else None

    if not data_path or not log_path:
        fallback = connection.execute(
            text(
                """
                SELECT TOP 1
                    LEFT(physical_name, LEN(physical_name) - CHARINDEX('\\', REVERSE(physical_name)) + 1) AS folder
                FROM sys.master_files
                WHERE database_id = 1
                ORDER BY file_id
                """
            )
        ).mappings().first()
        folder = fallback["folder"] if fallback else None
        if not folder:
            raise RuntimeError("No fue posible determinar dónde crear los archivos restaurados.")
        data_path = data_path or folder
        log_path = log_path or folder

    return Path(data_path), Path(log_path)


async def _save_upload(upload: UploadFile, destination: Path) -> int:
    written = 0
    with destination.open("wb") as output:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_BACKUP_SIZE_BYTES:
                output.close()
                destination.unlink(missing_ok=True)
                raise ValueError("El archivo .bak supera el límite actual de 2 GB.")
            output.write(chunk)
    await upload.close()
    return written


def _select_full_backup_set(connection, backup_path: Path) -> dict:
    escaped = _escape_sql_literal(str(backup_path))
    try:
        rows = connection.exec_driver_sql(
            f"RESTORE HEADERONLY FROM DISK = N'{escaped}'"
        ).mappings().all()
    except Exception as exc:
        raise RuntimeError(
            f"SQL Server no pudo leer la cabecera del backup '{backup_path}'. "
            f"Detalle original: {exc}"
        ) from exc

    if not rows:
        raise RuntimeError("El archivo no contiene ningún backup reconocible por SQL Server.")

    headers = [dict(row) for row in rows]
    full_backups = [row for row in headers if int(row.get("BackupType") or 0) == 1]

    if not full_backups:
        detected = []
        for row in headers:
            backup_type = int(row.get("BackupType") or 0)
            label = BACKUP_TYPE_LABELS.get(backup_type, f"Tipo {backup_type}")
            position = row.get("Position")
            detected.append(f"FILE={position}: {label}")

        raise RuntimeError(
            "El archivo .bak no contiene un backup COMPLETO de base de datos. "
            "Para una carga independiente Kenneth necesita un backup tipo Full. "
            f"Contenido detectado: {', '.join(detected)}. "
            "Crea en SSMS un backup con Backup type = Full y vuelve a cargarlo."
        )

    full_backups.sort(
        key=lambda row: (
            row.get("BackupFinishDate") is not None,
            row.get("BackupFinishDate"),
            int(row.get("Position") or 0),
        ),
        reverse=True,
    )
    selected = full_backups[0]

    position = int(selected.get("Position") or 0)
    if position < 1:
        raise RuntimeError("SQL Server no devolvió una posición válida para el backup Full.")

    return {
        "file_number": position,
        "database_name": selected.get("DatabaseName"),
        "backup_finish_date": selected.get("BackupFinishDate"),
        "backup_type": int(selected.get("BackupType") or 0),
        "recovery_model": selected.get("RecoveryModel"),
        "is_copy_only": bool(selected.get("IsCopyOnly")),
        "has_backup_checksums": bool(selected.get("HasBackupChecksums")),
        "is_damaged": bool(selected.get("IsDamaged")),
    }


def _read_file_list(connection, backup_path: Path, file_number: int) -> list[dict]:
    escaped = _escape_sql_literal(str(backup_path))
    try:
        rows = connection.exec_driver_sql(
            f"RESTORE FILELISTONLY FROM DISK = N'{escaped}' WITH FILE = {file_number}"
        ).mappings().all()
    except Exception as exc:
        raise RuntimeError(
            f"SQL Server encontró el backup Full (FILE={file_number}), pero no pudo leer sus archivos lógicos. "
            f"Detalle original: {exc}"
        ) from exc

    if not rows:
        raise RuntimeError("El backup Full seleccionado no contiene archivos restaurables.")

    return [dict(row) for row in rows]


def _verify_backup_raw(system_engine, backup_path: Path, file_number: int) -> None:
    """Valida el set exacto que será restaurado usando pyodbc directamente."""
    escaped = _escape_sql_literal(str(backup_path))
    sql = (
        f"RESTORE VERIFYONLY FROM DISK = N'{escaped}' "
        f"WITH FILE = {file_number}, CHECKSUM"
    )
    _execute_raw_sql_and_drain(system_engine, sql, operation="VERIFYONLY")


def _build_restore_sql(
    database_name: str,
    backup_path: Path,
    file_number: int,
    file_list: list[dict],
    data_dir: Path,
    log_dir: Path,
) -> str:
    moves: list[str] = []
    data_index = 0
    log_index = 0

    for row in file_list:
        logical_name = str(row.get("LogicalName") or "").strip()
        file_type = str(row.get("Type") or "D").upper()
        if not logical_name:
            continue

        if file_type == "L":
            log_index += 1
            suffix = "" if log_index == 1 else f"_{log_index}"
            target = log_dir / f"{database_name}_log{suffix}.ldf"
        else:
            data_index += 1
            suffix = "" if data_index == 1 else f"_{data_index}"
            extension = ".mdf" if data_index == 1 else ".ndf"
            target = data_dir / f"{database_name}{suffix}{extension}"

        moves.append(
            "MOVE N'{}' TO N'{}'".format(
                _escape_sql_literal(logical_name),
                _escape_sql_literal(str(target)),
            )
        )

    if not moves:
        raise RuntimeError("No fue posible determinar los archivos lógicos del backup.")

    return (
        f"RESTORE DATABASE {_quote_identifier(database_name)} "
        f"FROM DISK = N'{_escape_sql_literal(str(backup_path))}' "
        f"WITH FILE = {file_number}, {', '.join(moves)}, RECOVERY, CHECKSUM"
    )


def _execute_raw_sql_and_drain(system_engine, sql: str, operation: str) -> None:
    """Ejecuta RESTORE fuera de SQLAlchemy y consume todos los result sets de ODBC.

    RESTORE es una operación administrativa especial. Usar el cursor pyodbc directo,
    con autocommit real, evita que el estado transaccional/lifecycle de CursorResult de
    SQLAlchemy interfiera y garantiza que no seguimos hasta que ODBC terminó de procesar
    todos los resultados del comando.
    """
    raw = system_engine.raw_connection()
    cursor = None
    try:
        try:
            raw.autocommit = True
        except Exception:
            pass

        cursor = raw.cursor()
        cursor.execute(sql)

        while True:
            try:
                has_more = cursor.nextset()
            except Exception:
                has_more = False
            if not has_more:
                break
    except Exception as exc:
        raise RuntimeError(
            f"SQL Server falló durante {operation}. Detalle original: {exc}"
        ) from exc
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        try:
            raw.close()
        except Exception:
            pass


def _database_state(connection, database_name: str) -> str | None:
    return connection.exec_driver_sql(
        "SELECT state_desc FROM sys.databases WHERE name = ?",
        (database_name,),
    ).scalar_one_or_none()


def _restore_diagnostics(connection, database_name: str) -> dict:
    state_row = connection.exec_driver_sql(
        """
        SELECT name, state_desc, user_access_desc, recovery_model_desc,
               log_reuse_wait_desc, is_read_only
        FROM sys.databases
        WHERE name = ?
        """,
        (database_name,),
    ).mappings().first()

    request_row = connection.exec_driver_sql(
        """
        SELECT TOP 1 command, status, percent_complete,
               estimated_completion_time, wait_type, wait_resource
        FROM sys.dm_exec_requests
        WHERE command LIKE 'RESTORE%'
          AND database_id = DB_ID(?)
        ORDER BY start_time DESC
        """,
        (database_name,),
    ).mappings().first()

    return {
        "database": dict(state_row) if state_row else None,
        "active_restore_request": dict(request_row) if request_row else None,
    }


def _wait_until_online(system_engine, database_name: str, timeout_seconds: int = 60) -> tuple[str | None, dict]:
    deadline = time.monotonic() + timeout_seconds
    state: str | None = None
    diagnostics: dict = {}

    while time.monotonic() < deadline:
        with system_engine.connect() as connection:
            state = _database_state(connection, database_name)
            diagnostics = _restore_diagnostics(connection, database_name)

        if state == "ONLINE":
            return state, diagnostics
        if state in {"SUSPECT", "EMERGENCY", "RECOVERY_PENDING", "OFFLINE"}:
            return state, diagnostics
        time.sleep(1)

    return state, diagnostics


def _prepare_restored_database_access(system_engine, database_name: str, username: str | None) -> None:
    state, diagnostics = _wait_until_online(system_engine, database_name, timeout_seconds=60)

    if state != "ONLINE":
        raise RuntimeError(
            f"El RESTORE finalizó pero la base '{database_name}' quedó en estado "
            f"{state or 'desconocido'}. Diagnóstico SQL Server: {diagnostics}"
        )

    if not username:
        return

    db = _quote_identifier(database_name)
    login = _quote_identifier(username)
    try:
        with system_engine.connect() as connection:
            connection.exec_driver_sql(
                f"ALTER AUTHORIZATION ON DATABASE::{db} TO {login}"
            )
    except Exception as exc:
        raise RuntimeError(
            f"La base '{database_name}' se restauró y quedó ONLINE, pero el login '{username}' "
            "no pudo recibir acceso. En desarrollo usa una cuenta con permisos suficientes "
            f"(por ejemplo sysadmin). Detalle original: {exc}"
        ) from exc


def _cleanup_failed_restore(system_engine, database_name: str) -> None:
    try:
        with system_engine.connect() as connection:
            state = _database_state(connection, database_name)
            if state is None:
                return
        db = _quote_identifier(database_name)
        _execute_raw_sql_and_drain(
            system_engine,
            f"DROP DATABASE {db}",
            operation="limpieza de base temporal",
        )
    except Exception:
        pass


async def restore_sqlserver_backup(upload: UploadFile) -> dict:
    filename = upload.filename or "database.bak"
    if not filename.lower().endswith(".bak"):
        raise ValueError("Por ahora solo se aceptan backups de SQL Server con extensión .bak.")

    system_engine = database_manager.create_system_engine("master")
    staged_backup: Path | None = None
    database_name: str | None = None

    try:
        with system_engine.connect() as connection:
            restore_dir = _get_restore_directory(connection)
            data_dir, log_dir = _get_data_directories(connection)

            database_name = _safe_db_name(filename)
            staged_backup = restore_dir / f"{database_name}.bak"
            size_bytes = await _save_upload(upload, staged_backup)

            backup_set = _select_full_backup_set(connection, staged_backup)
            file_number = backup_set["file_number"]
            file_list = _read_file_list(connection, staged_backup, file_number)

        _verify_backup_raw(system_engine, staged_backup, file_number)

        restore_sql = _build_restore_sql(
            database_name=database_name,
            backup_path=staged_backup,
            file_number=file_number,
            file_list=file_list,
            data_dir=data_dir,
            log_dir=log_dir,
        )

        _execute_raw_sql_and_drain(
            system_engine,
            restore_sql,
            operation="RESTORE DATABASE",
        )

        active = database_manager.get_active_config()
        _prepare_restored_database_access(
            system_engine,
            database_name,
            active.get("username"),
        )

        database_manager.configure(
            server=active["server"],
            database=database_name,
            username=active.get("username"),
            password=active.get("password"),
            driver=active.get("driver") or "ODBC Driver 18 for SQL Server",
        )

        return {
            "restored": True,
            "database": database_name,
            "source_database": backup_set.get("database_name"),
            "backup_file_number": file_number,
            "backup_recovery_model": backup_set.get("recovery_model"),
            "backup_copy_only": backup_set.get("is_copy_only"),
            "backup_has_checksums": backup_set.get("has_backup_checksums"),
            "original_filename": filename,
            "size_bytes": size_bytes,
        }
    except Exception:
        if database_name:
            _cleanup_failed_restore(system_engine, database_name)
        raise
    finally:
        system_engine.dispose()
        if staged_backup is not None and staged_backup.exists():
            try:
                staged_backup.unlink()
            except OSError:
                pass

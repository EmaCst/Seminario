import os
import re
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import text

from app.database.database_manager import database_manager


MAX_BACKUP_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB para la primera versión


def _safe_db_name(filename: str) -> str:
    stem = Path(filename).stem
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_") or "uploaded"
    normalized = normalized[:48]
    return f"upload_{normalized}_{uuid.uuid4().hex[:8]}"


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _quote_identifier(value: str) -> str:
    return "[" + value.replace("]", "]]" ) + "]"


def _prepare_writable_directory(path: Path, create: bool = False) -> Path | None:
    """Devuelve la ruta si el backend puede escribir en ella.

    Para RESTORE necesitamos una carpeta compartida por dos actores:
    1) el proceso FastAPI debe poder guardar el .bak;
    2) el servicio de SQL Server debe poder leer ese mismo archivo.

    La comprobación de lectura de SQL Server se realiza después mediante
    RESTORE FILELISTONLY, por lo que aquí solo validamos la escritura local.
    """
    try:
        if create:
            path.mkdir(parents=True, exist_ok=True)
        elif not path.exists():
            return None

        probe = path / f".kenneth_write_test_{uuid.uuid4().hex}.tmp"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
        return path.resolve()
    except OSError:
        return None


def _get_restore_directory(connection) -> Path:
    # 1. Una ruta configurada explícitamente siempre tiene prioridad.
    configured = os.getenv("DB_RESTORE_DIR")
    if configured:
        configured_path = _prepare_writable_directory(
            Path(configured).expanduser(),
            create=True,
        )
        if configured_path is None:
            raise RuntimeError(
                f"DB_RESTORE_DIR apunta a una carpeta donde el backend no puede escribir: {configured}"
            )
        return configured_path

    # 2. En Windows usamos primero una carpeta neutral fuera de Program Files.
    # Es especialmente útil con SQL Server Express, cuyo directorio Backup
    # predeterminado normalmente requiere privilegios elevados para FastAPI.
    if os.name == "nt":
        shared_windows_path = _prepare_writable_directory(
            Path(r"C:\SQLBackups"),
            create=True,
        )
        if shared_windows_path is not None:
            return shared_windows_path

    # 3. Como último recurso intentamos la carpeta que reporta SQL Server,
    # pero solo si el proceso del backend también puede escribir ahí.
    row = connection.execute(
        text("SELECT CAST(SERVERPROPERTY('InstanceDefaultBackupPath') AS NVARCHAR(4000)) AS backup_path")
    ).mappings().first()

    backup_path = row["backup_path"] if row else None
    if backup_path:
        server_path = _prepare_writable_directory(Path(backup_path), create=False)
        if server_path is not None:
            return server_path

    raise RuntimeError(
        "No existe una carpeta compartida escribible para restaurar el backup. "
        "Crea C:\\SQLBackups o define DB_RESTORE_DIR en .env con una ruta donde "
        "el backend pueda escribir y el servicio de SQL Server pueda leer."
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


def _read_file_list(connection, backup_path: Path) -> list[dict]:
    escaped = _escape_sql_literal(str(backup_path))
    try:
        rows = connection.exec_driver_sql(
            f"RESTORE FILELISTONLY FROM DISK = N'{escaped}'"
        ).mappings().all()
    except Exception as exc:
        raise RuntimeError(
            "El backend pudo guardar el .bak, pero SQL Server no pudo leerlo. "
            f"Ruta usada: {backup_path}. Verifica permisos de lectura para el servicio de SQL Server. "
            f"Detalle: {exc}"
        ) from exc

    if not rows:
        raise RuntimeError("El backup no contiene archivos restaurables.")

    return [dict(row) for row in rows]


def _build_restore_sql(
    database_name: str,
    backup_path: Path,
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
        f"WITH {', '.join(moves)}, RECOVERY, STATS = 5"
    )


async def restore_sqlserver_backup(upload: UploadFile) -> dict:
    filename = upload.filename or "database.bak"
    if not filename.lower().endswith(".bak"):
        raise ValueError("Por ahora solo se aceptan backups de SQL Server con extensión .bak.")

    system_engine = database_manager.create_system_engine("master")
    staged_backup: Path | None = None

    try:
        with system_engine.connect() as connection:
            restore_dir = _get_restore_directory(connection)
            data_dir, log_dir = _get_data_directories(connection)

            database_name = _safe_db_name(filename)
            staged_backup = restore_dir / f"{database_name}.bak"
            size_bytes = await _save_upload(upload, staged_backup)

            file_list = _read_file_list(connection, staged_backup)
            restore_sql = _build_restore_sql(
                database_name=database_name,
                backup_path=staged_backup,
                file_list=file_list,
                data_dir=data_dir,
                log_dir=log_dir,
            )

            connection.exec_driver_sql(restore_sql)

        active = database_manager.get_active_config()
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
            "original_filename": filename,
            "size_bytes": size_bytes,
            "restore_directory": str(restore_dir),
        }
    finally:
        system_engine.dispose()
        if staged_backup is not None and staged_backup.exists():
            try:
                staged_backup.unlink()
            except OSError:
                pass

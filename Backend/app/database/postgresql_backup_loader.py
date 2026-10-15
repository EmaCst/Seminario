"""Import PostgreSQL pg_dump archives into a new, disposable-by-name database.

Supports pg_dump custom (.backup/.dump) and tar (.tar) archives, not arbitrary
plain SQL. An explicit opt-in is required because pg_restore executes DDL and
uploaded archives must be trusted. The previously active database is never
overwritten, renamed or dropped.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from threading import Lock
import uuid

from fastapi import UploadFile
from sqlalchemy import inspect

from app.database.database_manager import database_manager

logger = logging.getLogger(__name__)

MAX_BACKUP_SIZE_BYTES = 2 * 1024 * 1024 * 1024
ARCHIVE_EXTENSIONS = {".backup", ".dump", ".tar"}
_RESTORE_LOCK = Lock()
_TIMEOUT_SECONDS = 1800


def _safe_db_name(filename: str) -> str:
    """Generate a unique identifier; never trust filenames as SQL identifiers."""
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = Path(basename).stem
    normalized = re.sub(r"[^a-z0-9_]+", "_", stem.lower()).strip("_")[:40] or "postgres"
    return f"upload_{normalized}_{uuid.uuid4().hex[:12]}"


def _quote_identifier(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value):
        raise ValueError("Nombre interno de base de datos no válido.")
    return '"' + value.replace('"', '""') + '"'


def _pg_restore_executable() -> str:
    executable = os.getenv("PG_RESTORE_BIN", "pg_restore")
    resolved = shutil.which(executable)
    if not resolved:
        raise RuntimeError(
            "No encontré pg_restore. Instala las herramientas cliente de PostgreSQL, "
            "añade la carpeta bin de PostgreSQL al PATH del backend o configura "
            "PG_RESTORE_BIN con la ruta completa."
        )
    return resolved


def _client_environment(config: dict) -> dict[str, str]:
    # Explicit arguments win over libpq environment defaults, including on Windows.
    environment = dict(os.environ)
    for key in ("PGSERVICE", "PGSERVICEFILE", "PGHOSTADDR", "PGDATABASE",
                "PGPASSWORD", "PGUSER", "PGHOST", "PGPORT", "PGOPTIONS"):
        environment.pop(key, None)
    if config.get("password"):
        environment["PGPASSWORD"] = str(config["password"])
    environment["PGSSLMODE"] = str(config.get("sslmode") or "prefer")
    environment["PGCONNECT_TIMEOUT"] = "15"
    environment["PGPASSFILE"] = os.devnull  # Never silently use a workstation .pgpass.
    return environment


def _run_client(args: list[str], *, environment: dict | None = None,
                timeout: int = _TIMEOUT_SECONDS) -> str:
    try:
        completed = subprocess.run(
            args, env=environment, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, errors="replace",
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "PostgreSQL agotó el tiempo de espera durante la restauración."
        ) from exc
    except OSError as exc:
        raise RuntimeError("No pude ejecutar las herramientas de PostgreSQL.") from exc

    if completed.returncode != 0:
        # Do not include credentials or command-line parameters in error text.
        details = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            "pg_restore no pudo procesar el respaldo. "
            f"Detalle: {details[-1000:] or f'código {completed.returncode}'}"
        )
    return completed.stdout


def _validate_archive(archive: Path, extension: str, tool: str) -> None:
    with archive.open("rb") as source:
        first_bytes = source.read(512)
    if extension in {".backup", ".dump"} and not first_bytes.startswith(b"PGDMP"):
        raise ValueError(
            "El archivo no contiene un respaldo PostgreSQL en formato Custom. "
            "Créalo con pg_dump -Fc. Los archivos SQL de texto no se admiten."
        )
    if extension == ".tar" and first_bytes.startswith(b"PGDMP"):
        raise ValueError("El archivo es Custom, no TAR; utiliza .backup o .dump.")
    # pg_restore verifies the archive structure before creating any database.
    listing = _run_client([tool, "--list", str(archive)], timeout=120)
    if not re.search(r"(?m)^\s*\d+;\s+\d+\s+\d+\s+TABLE\s", listing):
        raise ValueError(
            "El respaldo no contiene tablas restaurables. "
            "Kenneth necesita al menos una tabla para analizar la base."
        )


async def _save_upload(upload: UploadFile, destination: Path) -> int:
    size = 0
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BACKUP_SIZE_BYTES:
                    raise ValueError("El respaldo supera el límite actual de 2 GB.")
                output.write(chunk)
        if size == 0:
            raise ValueError("El archivo de respaldo está vacío.")
        return size
    finally:
        await upload.close()


def _admin_engine(config: dict):
    """Use the ORIGINAL PostgreSQL connection for create and cleanup.

    An independent engine avoids touching a different provider if someone
    changes Kenneth's active connection while a long restore is running.
    """
    return database_manager._build_postgresql_engine(
        host=config["host"], database=config["database"],
        port=config["port"], username=config["username"],
        password=config.get("password"), sslmode=config.get("sslmode") or "prefer",
    )


def _create_database(name: str, config: dict) -> None:
    # CREATE DATABASE cannot run inside a PostgreSQL transaction.
    admin = _admin_engine(config)
    try:
        with admin.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.exec_driver_sql(
                f"CREATE DATABASE {_quote_identifier(name)} TEMPLATE template0"
            )
    finally:
        admin.dispose()


def _drop_created_database(name: str, config: dict) -> None:
    # Drop ONLY a new database created successfully by this upload request.
    admin = None
    try:
        admin = _admin_engine(config)
        with admin.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.exec_driver_sql(f"DROP DATABASE {_quote_identifier(name)}")
    except Exception:
        logger.exception("No pude limpiar la base de restauración fallida %s", name)
    finally:
        if admin is not None:
            admin.dispose()


def _restore_archive(archive: Path, database_name: str, config: dict, tool: str) -> None:
    command = [
        tool,
        "--host", str(config["host"]),
        "--port", str(config["port"]),
        "--username", str(config["username"]),
        "--dbname", database_name,
        "--no-password",
        "--no-owner",
        "--no-privileges",
        "--no-tablespaces",
        "--no-publications",
        "--no-subscriptions",
        "--no-security-labels",
        "--exit-on-error",
        "--single-transaction",
        str(archive),
    ]
    _run_client(command, environment=_client_environment(config))


def _verify_restored_database(database_name: str, config: dict) -> list[str]:
    verifier = database_manager._build_postgresql_engine(
        host=config["host"], port=config["port"], database=database_name,
        username=config["username"], password=config.get("password"),
        sslmode=config.get("sslmode") or "prefer",
    )
    try:
        with verifier.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        tables = inspect(verifier).get_table_names()
        if not tables:
            raise RuntimeError(
                "La restauración terminó, pero no hay tablas visibles en el esquema "
                "public de PostgreSQL. Kenneth no activará una base vacía."
            )
        return tables
    finally:
        verifier.dispose()


def _restore_staged(archive: Path, config: dict, tool: str, filename: str,
                    size_bytes: int) -> dict:
    name = _safe_db_name(filename)
    created = False
    try:
        _create_database(name, config)
        created = True
        _restore_archive(archive, name, config, tool)
        tables = _verify_restored_database(name, config)
        # Switch only after a fully successful restore and connectivity check.
        database_manager.configure_postgresql(
            host=config["host"], port=config["port"], database=name,
            username=config["username"], password=config.get("password"),
            sslmode=config.get("sslmode") or "prefer",
        )
        created = False
        return {
            "restored": True,
            "database": name,
            "original_filename": filename,
            "size_bytes": size_bytes,
            "table_count": len(tables),
            "format": Path(filename).suffix.lower().lstrip("."),
        }
    except Exception:
        if created:
            _drop_created_database(name, config)
        raise


async def restore_postgresql_backup(upload: UploadFile) -> dict:
    """Restore only when an existing PostgreSQL connection was activated.

    Requires PG_BACKUP_UPLOAD_ENABLED=1. Administrators must only upload
    trusted dumps; their schema SQL is executed using the connected role.
    """
    filename = upload.filename or ""
    extension = Path(filename.replace("\\", "/")).suffix.lower()
    if extension not in ARCHIVE_EXTENSIONS:
        await upload.close()
        raise ValueError(
            "Carga archivos .backup, .dump (Custom) o .tar de pg_dump. "
            "Los .sql de texto no se admiten por seguridad."
        )
    if os.getenv("PG_BACKUP_UPLOAD_ENABLED", "").strip().lower() not in (
        "1", "true", "yes"
    ):
        await upload.close()
        raise ValueError(
            "La restauración PostgreSQL está deshabilitada por seguridad. "
            "Un administrador debe definir PG_BACKUP_UPLOAD_ENABLED=1 "
            "en Backend/.env y reiniciar el backend."
        )
    try:
        config = database_manager.get_active_config()
    except RuntimeError as exc:
        await upload.close()
        raise ValueError(
            "Primero conecta una base PostgreSQL existente desde Configuración."
        ) from exc
    if config.get("provider") != "postgresql":
        await upload.close()
        raise ValueError(
            "La fuente activa no es PostgreSQL. Conecta PostgreSQL antes de subir el respaldo."
        )
    if not _RESTORE_LOCK.acquire(blocking=False):
        await upload.close()
        raise ValueError("Ya se está restaurando un respaldo. Espera a que termine.")

    try:
        tool = _pg_restore_executable()
        # TemporaryDirectory deletes uploaded archive on success or failure.
        with tempfile.TemporaryDirectory(prefix="kenneth_pg_restore_") as folder:
            archive = Path(folder) / f"backup{extension}"
            size_bytes = await _save_upload(upload, archive)
            await asyncio.to_thread(_validate_archive, archive, extension, tool)
            return await asyncio.to_thread(
                _restore_staged, archive, config, tool, filename, size_bytes
            )
    finally:
        _RESTORE_LOCK.release()
        await upload.close()

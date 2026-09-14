from __future__ import annotations

from threading import RLock
from time import monotonic

from app.database.database_manager import database_manager
from app.database.inspector import inspect_database
from app.database.serializer import schema_to_json


_CACHE_TTL_SECONDS = 300
_cache_lock = RLock()
_cache_signature: tuple | None = None
_cache_value: str | None = None
_cache_created_at = 0.0


def _connection_signature() -> tuple:
    status = database_manager.status()
    return (
        status.get("connected"),
        status.get("provider"),
        status.get("server") or status.get("host"),
        status.get("database"),
    )


def clear_database_context_cache() -> None:
    global _cache_signature, _cache_value, _cache_created_at
    with _cache_lock:
        _cache_signature = None
        _cache_value = None
        _cache_created_at = 0.0


def get_database_context(force_refresh: bool = False) -> str:
    """Devuelve el esquema de la base activa en JSON con caché de corta duración.

    Antes cada pregunta volvía a inspeccionar tablas, columnas, PK y FK. En bases
    medianas eso añade latencia innecesaria. La caché se invalida automáticamente
    cuando cambia la conexión activa y expira a los cinco minutos.
    """

    global _cache_signature, _cache_value, _cache_created_at

    signature = _connection_signature()
    now = monotonic()

    with _cache_lock:
        cache_is_valid = (
            not force_refresh
            and _cache_value is not None
            and _cache_signature == signature
            and (now - _cache_created_at) < _CACHE_TTL_SECONDS
        )
        if cache_is_valid:
            return _cache_value

    schema = inspect_database()
    value = schema_to_json(schema)

    with _cache_lock:
        _cache_signature = signature
        _cache_value = value
        _cache_created_at = monotonic()

    return value

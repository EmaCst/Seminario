from __future__ import annotations

import json
from threading import RLock
from time import monotonic

from app.database.database_manager import database_manager
from app.database.inspector import inspect_database
from app.database.serializer import schema_to_json


_CACHE_TTL_SECONDS = 300
_cache_lock = RLock()
_cache_signature: tuple | None = None
_cache_value: str | None = None
_cache_compact_value: str | None = None
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
    global _cache_signature, _cache_value, _cache_compact_value, _cache_created_at
    with _cache_lock:
        _cache_signature = None
        _cache_value = None
        _cache_compact_value = None
        _cache_created_at = 0.0


def _build_compact_context(raw_json: str) -> str:
    """Reduce el JSON del esquema a una representación corta para el LLM.

    Conserva nombres, tipos, PK y FK, que es lo que Gemma realmente necesita
    para generar SQL. Se omiten campos verbosos como nullable para reducir tokens.
    """
    data = json.loads(raw_json)
    lines = [f"DATABASE: {data.get('database', '')}", "TABLES:"]

    for table_name, table in (data.get("tables") or {}).items():
        columns = table.get("columns") or []
        column_text = ", ".join(
            f"{column.get('name')}:{column.get('type')}"
            for column in columns
        )
        pk = table.get("primary_key") or []
        pk_text = f" | PK({', '.join(pk)})" if pk else ""
        lines.append(f"- {table_name}({column_text}){pk_text}")

    relationships = data.get("relationships") or []
    if relationships:
        lines.append("RELATIONSHIPS:")
        for relation in relationships:
            lines.append(
                "- "
                f"{relation.get('table')}.{relation.get('column')} -> "
                f"{relation.get('references_table')}.{relation.get('references_column')}"
            )

    return "\n".join(lines)


def _load_context(force_refresh: bool = False) -> tuple[str, str]:
    global _cache_signature, _cache_value, _cache_compact_value, _cache_created_at

    signature = _connection_signature()
    now = monotonic()

    with _cache_lock:
        cache_is_valid = (
            not force_refresh
            and _cache_value is not None
            and _cache_compact_value is not None
            and _cache_signature == signature
            and (now - _cache_created_at) < _CACHE_TTL_SECONDS
        )
        if cache_is_valid:
            return _cache_value, _cache_compact_value

    schema = inspect_database()
    value = schema_to_json(schema)
    compact_value = _build_compact_context(value)

    with _cache_lock:
        _cache_signature = signature
        _cache_value = value
        _cache_compact_value = compact_value
        _cache_created_at = monotonic()

    return value, compact_value


def get_database_context(force_refresh: bool = False) -> str:
    """Devuelve el esquema completo en JSON con caché de corta duración."""
    value, _ = _load_context(force_refresh=force_refresh)
    return value


def get_compact_database_context(force_refresh: bool = False) -> str:
    """Devuelve una versión compacta del esquema optimizada para prompts."""
    _, compact_value = _load_context(force_refresh=force_refresh)
    return compact_value

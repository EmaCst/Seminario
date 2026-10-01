import re

from app.database.inspector import inspect_database


FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "EXEC",
    "EXECUTE",
    "MERGE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "DENY",
}


class SQLValidationError(Exception):
    pass


def extract_tables(sql: str) -> set[str]:
    """Extrae tablas físicas y referencias CTE usadas después de FROM/JOIN."""
    pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+(?:"
        r"\[([^\]]+)\]"
        r"|\"([^\"]+)\""
        r"|([a-zA-Z_][a-zA-Z0-9_]*)"
        r")",
        re.IGNORECASE,
    )

    tables: set[str] = set()
    for match in pattern.finditer(sql):
        table = next((group for group in match.groups() if group), None)
        if table:
            tables.add(table)

    return tables


def extract_cte_names(sql: str) -> set[str]:
    """Obtiene nombres de CTE declaradas con WITH para no tratarlas como tablas físicas."""
    if not re.match(r"^\s*WITH\b", sql, re.IGNORECASE):
        return set()

    names: set[str] = set()
    pattern = re.compile(
        r"(?:\bWITH\b|,)\s*(?:"
        r"\[([^\]]+)\]"
        r"|\"([^\"]+)\""
        r"|([a-zA-Z_][a-zA-Z0-9_]*)"
        r")\s+AS\s*\(",
        re.IGNORECASE,
    )

    for match in pattern.finditer(sql):
        name = next((group for group in match.groups() if group), None)
        if name:
            names.add(name.lower())

    return names


def _is_read_only_query(sql: str) -> bool:
    normalized = sql.lstrip().upper()
    if normalized.startswith("SELECT"):
        return True
    if normalized.startswith("WITH"):
        # Una CTE válida para Kenneth debe terminar ejecutando un SELECT.
        return bool(re.search(r"\bSELECT\b", normalized))
    return False


def validate_sql(sql: str) -> bool:
    """Valida consultas de solo lectura contra el esquema real activo.

    Se permiten SELECT directos y CTEs (WITH ... SELECT), necesarias para
    comparaciones entre periodos, rankings y consultas analíticas complejas.
    """
    if not sql:
        raise SQLValidationError("La consulta SQL está vacía.")

    normalized = sql.strip().upper()

    if not _is_read_only_query(sql):
        raise SQLValidationError("Solo se permiten consultas SELECT de solo lectura.")

    statements = [statement.strip() for statement in sql.split(";") if statement.strip()]
    if len(statements) > 1:
        raise SQLValidationError("Solo se permite una consulta SQL por solicitud.")

    for keyword in FORBIDDEN_KEYWORDS:
        pattern = rf"\b{re.escape(keyword)}\b"
        if re.search(pattern, normalized, re.IGNORECASE):
            raise SQLValidationError(f"Operación no permitida detectada: {keyword}")

    schema = inspect_database()
    valid_tables = {table.lower() for table in schema.tables.keys()}
    cte_names = extract_cte_names(sql)
    used_tables = extract_tables(sql)

    physical_tables = {
        table for table in used_tables
        if table.lower() not in cte_names
    }

    if not physical_tables:
        raise SQLValidationError("No se pudo identificar ninguna tabla real en la consulta.")

    for table in physical_tables:
        if table.lower() not in valid_tables:
            raise SQLValidationError(f"La tabla '{table}' no existe en la base de datos.")

    return True

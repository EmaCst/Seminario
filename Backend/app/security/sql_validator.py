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
    """Extrae tablas utilizadas después de FROM y JOIN en SQL Server/PostgreSQL."""

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


def validate_sql(sql: str) -> bool:
    """Valida consultas de solo lectura contra el esquema real activo."""

    if not sql:
        raise SQLValidationError("La consulta SQL está vacía.")

    normalized = sql.strip().upper()

    if not normalized.startswith("SELECT"):
        raise SQLValidationError("Solo se permiten consultas SELECT.")

    statements = [statement.strip() for statement in sql.split(";") if statement.strip()]
    if len(statements) > 1:
        raise SQLValidationError("Solo se permite una consulta SQL por solicitud.")

    for keyword in FORBIDDEN_KEYWORDS:
        pattern = rf"\b{re.escape(keyword)}\b"
        if re.search(pattern, normalized, re.IGNORECASE):
            raise SQLValidationError(f"Operación no permitida detectada: {keyword}")

    schema = inspect_database()
    valid_tables = {table.lower() for table in schema.tables.keys()}
    used_tables = extract_tables(sql)

    if not used_tables:
        raise SQLValidationError("No se pudo identificar ninguna tabla en la consulta.")

    for table in used_tables:
        if table.lower() not in valid_tables:
            raise SQLValidationError(f"La tabla '{table}' no existe en la base de datos.")

    return True

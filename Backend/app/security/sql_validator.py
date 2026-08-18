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
    """
    Extrae las tablas utilizadas después de FROM y JOIN.
    """

    pattern = r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)"

    matches = re.findall(
        pattern,
        sql,
        re.IGNORECASE
    )

    return set(matches)


def validate_sql(sql: str) -> bool:
    """
    Valida que el SQL generado:

    - Sea únicamente de lectura.
    - Sea un solo statement.
    - No contenga operaciones peligrosas.
    - Utilice únicamente tablas reales de la base de datos.
    """

    if not sql:
        raise SQLValidationError(
            "La consulta SQL está vacía."
        )

    normalized = sql.strip().upper()

    # ==========================================
    # SOLO SELECT
    # ==========================================

    if not normalized.startswith("SELECT"):
        raise SQLValidationError(
            "Solo se permiten consultas SELECT."
        )

    # ==========================================
    # UN SOLO STATEMENT
    # ==========================================

    statements = [
        statement.strip()
        for statement in sql.split(";")
        if statement.strip()
    ]

    if len(statements) > 1:
        raise SQLValidationError(
            "Solo se permite una consulta SQL por solicitud."
        )

    # ==========================================
    # PALABRAS PROHIBIDAS
    # ==========================================

    for keyword in FORBIDDEN_KEYWORDS:

        pattern = rf"\b{re.escape(keyword)}\b"

        if re.search(
            pattern,
            normalized,
            re.IGNORECASE
        ):
            raise SQLValidationError(
                f"Operación no permitida detectada: {keyword}"
            )

    # ==========================================
    # OBTENER ESQUEMA REAL
    # ==========================================

    schema = inspect_database()

    valid_tables = {
        table.lower()
        for table in schema.tables.keys()
    }

    # ==========================================
    # EXTRAER TABLAS DEL SQL
    # ==========================================

    used_tables = extract_tables(sql)

    if not used_tables:
        raise SQLValidationError(
            "No se pudo identificar ninguna tabla en la consulta."
        )

    # ==========================================
    # VALIDAR TABLAS
    # ==========================================

    for table in used_tables:

        if table.lower() not in valid_tables:

            raise SQLValidationError(
                f"La tabla '{table}' no existe en la base de datos."
            )

    return True
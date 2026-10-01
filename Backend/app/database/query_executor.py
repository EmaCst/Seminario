from app.database.connection import get_connection
from app.security.sql_validator import validate_sql


def execute_query(sql: str) -> list[dict]:
    """
    Valida y ejecuta una consulta SELECT.

    Devuelve los resultados como una lista de diccionarios.
    """

    validate_sql(sql)

    with get_connection() as connection:

        result = connection.exec_driver_sql(sql)

        columns = list(result.keys())

        rows = result.fetchall()

        return [
            dict(zip(columns, row))
            for row in rows
        ]
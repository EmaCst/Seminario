import re


def normalize_sql(sql: str) -> str:
    """
    Limpia y normaliza el SQL generado por la IA
    para Microsoft SQL Server.
    """

    sql = sql.strip()

    # ==========================================
    # ELIMINAR BLOQUES MARKDOWN
    # ==========================================

    if sql.startswith("```sql"):
        sql = sql[6:]

    elif sql.startswith("```"):
        sql = sql[3:]

    if sql.endswith("```"):
        sql = sql[:-3]

    sql = sql.strip()

    # ==========================================
    # CONVERTIR LIMIT -> TOP
    # ==========================================

    limit_match = re.search(
        r"\s+LIMIT\s+(\d+)\s*;?\s*$",
        sql,
        re.IGNORECASE
    )

    if limit_match:

        limit = limit_match.group(1)

        # Eliminar LIMIT del final
        sql = sql[:limit_match.start()].rstrip()

        # SELECT DISTINCT necesita TOP después de DISTINCT
        if re.match(
            r"^\s*SELECT\s+DISTINCT\b",
            sql,
            re.IGNORECASE
        ):

            sql = re.sub(
                r"^(\s*SELECT\s+DISTINCT)\b",
                rf"\1 TOP {limit}",
                sql,
                count=1,
                flags=re.IGNORECASE
            )

        else:

            sql = re.sub(
                r"^(\s*SELECT)\b",
                rf"\1 TOP {limit}",
                sql,
                count=1,
                flags=re.IGNORECASE
            )

    # ==========================================
    # ASEGURAR PUNTO Y COMA
    # ==========================================

    sql = sql.rstrip(";").strip() + ";"

    return sql
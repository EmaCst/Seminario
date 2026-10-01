import re


def normalize_sql(sql: str, dialect: str = "sqlserver") -> str:
    """Limpia el SQL generado y aplica normalización específica del motor."""

    sql = sql.strip()

    if sql.startswith("```sql"):
        sql = sql[6:]
    elif sql.startswith("```"):
        sql = sql[3:]

    if sql.endswith("```"):
        sql = sql[:-3]

    sql = sql.strip()

    if dialect == "sqlserver":
        limit_match = re.search(
            r"\s+LIMIT\s+(\d+)\s*;?\s*$",
            sql,
            re.IGNORECASE,
        )

        if limit_match:
            limit = limit_match.group(1)
            sql = sql[:limit_match.start()].rstrip()

            if re.match(r"^\s*SELECT\s+DISTINCT\b", sql, re.IGNORECASE):
                sql = re.sub(
                    r"^(\s*SELECT\s+DISTINCT)\b",
                    rf"\1 TOP {limit}",
                    sql,
                    count=1,
                    flags=re.IGNORECASE,
                )
            else:
                sql = re.sub(
                    r"^(\s*SELECT)\b",
                    rf"\1 TOP {limit}",
                    sql,
                    count=1,
                    flags=re.IGNORECASE,
                )

    elif dialect == "postgresql":
        # Defensa por si el modelo mezcla TOP de SQL Server con PostgreSQL.
        top_match = re.match(
            r"^(\s*SELECT\s+)(?:DISTINCT\s+)?TOP\s+(\d+)\s+",
            sql,
            re.IGNORECASE,
        )
        if top_match:
            limit = top_match.group(2)
            distinct = bool(re.match(r"^\s*SELECT\s+DISTINCT", sql, re.IGNORECASE))
            sql = re.sub(
                r"^(\s*SELECT\s+)(?:DISTINCT\s+)?TOP\s+\d+\s+",
                r"\1DISTINCT " if distinct else r"\1",
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
            sql = sql.rstrip("; ") + f" LIMIT {limit}"

    return sql.rstrip(";").strip() + ";"

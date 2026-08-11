from sqlalchemy import inspect

from app.database.connection import engine


IGNORED_TABLES = {
    "sysdiagrams"
}


def inspect_database():

    inspector = inspect(engine)

    schema = {
        "database": "Seminario1",
        "tables": {},
        "relationships": []
    }

    # ==========================================
    # TABLAS
    # ==========================================

    tables = inspector.get_table_names()

    for table in tables:

        if table in IGNORED_TABLES:
            continue

        columns = inspector.get_columns(table)
        primary_key = inspector.get_pk_constraint(table)

        schema["tables"][table] = {
            "columns": [],
            "primary_key": primary_key.get("constrained_columns", [])
        }

        for column in columns:

            schema["tables"][table]["columns"].append({
                "name": column["name"],
                "type": str(column["type"]),
                "nullable": column["nullable"]
            })

    # ==========================================
    # FOREIGN KEYS
    # ==========================================

    for table in schema["tables"]:

        foreign_keys = inspector.get_foreign_keys(table)

        for fk in foreign_keys:

            constrained_columns = fk.get("constrained_columns", [])
            referred_columns = fk.get("referred_columns", [])

            if not constrained_columns or not referred_columns:
                continue

            relationship = {
                "table": table,
                "column": constrained_columns[0],
                "references_table": fk["referred_table"],
                "references_column": referred_columns[0]
            }

            schema["relationships"].append(relationship)

    return schema


if __name__ == "__main__":

    schema = inspect_database()

    print("\n===== BASE DE DATOS =====")
    print(schema["database"])

    print("\n===== TABLAS =====")

    for table, information in schema["tables"].items():

        print(f"\nTabla: {table}")

        print(
            f"  Primary Key: "
            f"{information['primary_key']}"
        )

        for column in information["columns"]:

            print(
                f"  - {column['name']} "
                f"({column['type']}) "
                f"Nullable: {column['nullable']}"
            )

    print("\n===== RELACIONES =====")

    for relationship in schema["relationships"]:

        print(
            f"{relationship['table']}."
            f"{relationship['column']}"
            f" -> "
            f"{relationship['references_table']}."
            f"{relationship['references_column']}"
        )
from sqlalchemy import inspect

from app.database.connection import engine
from app.database.schema import (
    ColumnSchema,
    DatabaseSchema,
    RelationshipSchema,
    TableSchema,
)


IGNORED_TABLES = {
    "sysdiagrams"
}


def inspect_database() -> DatabaseSchema:

    inspector = inspect(engine)

    schema = DatabaseSchema(
        database="Seminario1"
    )

    # ==========================================
    # TABLAS
    # ==========================================

    tables = inspector.get_table_names()

    for table_name in tables:

        if table_name in IGNORED_TABLES:
            continue

        table_schema = TableSchema(
            name=table_name
        )

        # Columnas

        columns = inspector.get_columns(table_name)

        for column in columns:

            table_schema.columns.append(
                ColumnSchema(
                    name=column["name"],
                    type=str(column["type"]),
                    nullable=column["nullable"],
                )
            )

        # Primary Key

        primary_key = inspector.get_pk_constraint(
            table_name
        )

        table_schema.primary_key = (
            primary_key.get(
                "constrained_columns",
                []
            )
        )

        schema.tables[table_name] = table_schema

    # ==========================================
    # FOREIGN KEYS
    # ==========================================

    for table_name in schema.tables:

        foreign_keys = inspector.get_foreign_keys(
            table_name
        )

        for fk in foreign_keys:

            constrained_columns = fk.get(
                "constrained_columns",
                []
            )

            referred_columns = fk.get(
                "referred_columns",
                []
            )

            if not constrained_columns:
                continue

            if not referred_columns:
                continue

            relationship = RelationshipSchema(
                table=table_name,
                column=constrained_columns[0],
                references_table=fk[
                    "referred_table"
                ],
                references_column=referred_columns[0],
            )

            schema.relationships.append(
                relationship
            )

    return schema


if __name__ == "__main__":

    schema = inspect_database()

    print("\n===== BASE DE DATOS =====")
    print(schema.database)

    print("\n===== TABLAS =====")

    for table_name, table in schema.tables.items():

        print(f"\nTabla: {table_name}")

        print(
            f"Primary Key: "
            f"{table.primary_key}"
        )

        for column in table.columns:

            print(
                f"  - {column.name} "
                f"({column.type}) "
                f"Nullable: {column.nullable}"
            )

    print("\n===== RELACIONES =====")

    for relationship in schema.relationships:

        print(
            f"{relationship.table}."
            f"{relationship.column}"
            f" -> "
            f"{relationship.references_table}."
            f"{relationship.references_column}"
        )
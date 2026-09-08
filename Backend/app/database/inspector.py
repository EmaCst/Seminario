import json

from sqlalchemy import inspect

from app.database.connection import get_engine
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
    """Inspecciona dinámicamente la base de datos actualmente conectada."""

    engine = get_engine()
    inspector = inspect(engine)

    # No quemamos el nombre de la BD: SQLAlchemy ya conoce la BD activa.
    database_name = engine.url.database or "unknown"

    schema = DatabaseSchema(
        database=database_name
    )

    tables = inspector.get_table_names()

    for table_name in tables:
        if table_name in IGNORED_TABLES:
            continue

        table_schema = TableSchema(
            name=table_name
        )

        columns = inspector.get_columns(table_name)

        for column in columns:
            table_schema.columns.append(
                ColumnSchema(
                    name=column["name"],
                    type=str(column["type"]),
                    nullable=column["nullable"],
                )
            )

        primary_key = inspector.get_pk_constraint(
            table_name
        )

        table_schema.primary_key = primary_key.get(
            "constrained_columns",
            []
        )

        schema.tables[table_name] = table_schema

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

            if not constrained_columns or not referred_columns:
                continue

            referred_table = fk.get("referred_table")

            if not referred_table:
                continue

            # Se conserva el modelo actual (una columna por RelationshipSchema).
            # Las FK compuestas pueden ampliarse posteriormente en schema.py.
            for from_column, to_column in zip(
                constrained_columns,
                referred_columns
            ):
                schema.relationships.append(
                    RelationshipSchema(
                        table=table_name,
                        column=from_column,
                        references_table=referred_table,
                        references_column=to_column,
                    )
                )

    return schema


if __name__ == "__main__":
    schema = inspect_database()

    print("\n===== BASE DE DATOS =====")
    print(schema.database)

    print("\n===== TABLAS =====")

    for table_name, table in schema.tables.items():
        print(f"\nTabla: {table_name}")
        print(f"Primary Key: {table.primary_key}")

        for column in table.columns:
            print(
                f"  - {column.name} "
                f"({column.type}) "
                f"Nullable: {column.nullable}"
            )

    print("\n===== RELACIONES =====")

    for relationship in schema.relationships:
        print(
            f"{relationship.table}.{relationship.column}"
            f" -> "
            f"{relationship.references_table}."
            f"{relationship.references_column}"
        )

    print("\n===== JSON SCHEMA =====")
    print(
        json.dumps(
            schema.to_dict(),
            indent=4,
            ensure_ascii=False
        )
    )

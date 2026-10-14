import json
import re
import unicodedata

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



def _normalized_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", value)


def _table_aliases(name: str) -> set[str]:
    value = _normalized_name(name)
    aliases = {value}
    if value.endswith("ies"):
        aliases.add(value[:-3] + "y")
    if value.endswith("es"):
        aliases.add(value[:-2])
    if value.endswith("s"):
        aliases.add(value[:-1])
    return aliases


def _infer_identifier_relationships(schema: DatabaseSchema) -> None:
    """Infer only unambiguous identifier-to-primary-key links.

    These are suggestions for read-only analysis; no database constraints are changed.
    Avoid guessing relationships to non-unique columns or ambiguous parent tables.
    """
    existing = {(rel.table, rel.column) for rel in schema.relationships}
    parents = {}
    for table in schema.tables.values():
        if len(table.primary_key) != 1:
            continue
        pk = table.primary_key[0]
        aliases = _table_aliases(table.name)
        for alias in aliases:
            parents.setdefault(alias, []).append((table.name, pk))

    for table in schema.tables.values():
        for column in table.columns:
            if (table.name, column.name) in existing or column.name in table.primary_key:
                continue
            normalized = _normalized_name(column.name)
            # Both producto_id and id_producto are common business schemas.
            if normalized.endswith("id") and len(normalized) > 2:
                prefix = normalized[:-2]
            elif normalized.startswith("id") and len(normalized) > 2:
                prefix = normalized[2:]
            else:
                continue
            candidates = set(parents.get(prefix, []))
            candidates.discard((table.name, column.name))
            if len(candidates) != 1:
                continue
            parent_table, parent_pk = next(iter(candidates))
            if parent_table == table.name:
                continue
            schema.relationships.append(RelationshipSchema(
                table=table.name, column=column.name,
                references_table=parent_table, references_column=parent_pk,
            ))
            existing.add((table.name, column.name))


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

    _infer_identifier_relationships(schema)
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

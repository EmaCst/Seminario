from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnSchema:
    name: str
    type: str
    nullable: bool


@dataclass
class TableSchema:
    name: str
    columns: list[ColumnSchema] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)


@dataclass
class RelationshipSchema:
    table: str
    column: str
    references_table: str
    references_column: str


@dataclass
class DatabaseSchema:
    database: str
    tables: dict[str, TableSchema] = field(default_factory=dict)
    relationships: list[RelationshipSchema] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:

        return {
            "database": self.database,
            "tables": {
                table_name: {
                    "columns": [
                        {
                            "name": column.name,
                            "type": column.type,
                            "nullable": column.nullable,
                        }
                        for column in table.columns
                    ],
                    "primary_key": table.primary_key,
                }
                for table_name, table in self.tables.items()
            },
            "relationships": [
                {
                    "table": relationship.table,
                    "column": relationship.column,
                    "references_table": relationship.references_table,
                    "references_column": relationship.references_column,
                }
                for relationship in self.relationships
            ],
        }
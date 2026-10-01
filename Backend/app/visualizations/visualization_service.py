import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.database.database_manager import database_manager
from app.database.inspector import inspect_database
from app.database.query_executor import execute_query


VisualizationType = Literal["kpi", "bar", "line", "donut", "table"]
AggregationType = Literal["count", "sum", "avg", "min", "max"]


class VisualizationFilter(BaseModel):
    column: str
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "contains", "in"] = "eq"
    value: str | int | float | bool | list[str | int | float]


class VisualizationDefinition(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    visualization: VisualizationType
    table: str
    metric: str | None = None
    aggregation: AggregationType = "count"
    group_by: str | None = None
    filters: list[VisualizationFilter] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_shape(self):
        if self.aggregation != "count" and not self.metric:
            raise ValueError("Selecciona una métrica para esta agregación.")
        if self.visualization in {"bar", "line", "donut"} and not self.group_by:
            raise ValueError("Esta visualización necesita una dimensión para agrupar.")
        return self


def _quote(identifier: str) -> str:
    provider = database_manager.status().get("provider")
    if provider in {"postgresql", "excel"}:
        return '"' + identifier.replace('"', '""') + '"'
    return "[" + identifier.replace("]", "]]") + "]"


def _column_kind(type_name: str) -> str:
    value = type_name.lower()
    if any(token in value for token in ("int", "numeric", "decimal", "real", "float", "double", "money")):
        return "number"
    if any(token in value for token in ("date", "time")):
        return "date"
    if any(token in value for token in ("bool", "bit")):
        return "boolean"
    return "text"


def get_visualization_catalog() -> dict:
    schema = inspect_database()
    tables = []
    for table in schema.tables.values():
        columns = [
            {
                "name": column.name,
                "type": column.type,
                "kind": _column_kind(column.type),
                "aggregations": ["count", "sum", "avg", "min", "max"]
                if _column_kind(column.type) == "number"
                else ["count"],
            }
            for column in table.columns
        ]
        tables.append({
            "name": table.name,
            "primary_key": table.primary_key,
            "columns": columns,
        })

    return {
        "database": schema.database,
        "provider": database_manager.status().get("provider"),
        "visualizations": ["kpi", "bar", "line", "donut", "table"],
        "tables": tables,
        "relationships": [
            {
                "table": rel.table,
                "column": rel.column,
                "references_table": rel.references_table,
                "references_column": rel.references_column,
            }
            for rel in schema.relationships
        ],
    }


def _resolve_definition(definition: VisualizationDefinition):
    schema = inspect_database()
    table = schema.tables.get(definition.table)
    if table is None:
        raise ValueError(f"La tabla '{definition.table}' no existe.")

    columns = {column.name: column for column in table.columns}
    requested = [definition.metric, definition.group_by] + [item.column for item in definition.filters]
    for column in (item for item in requested if item):
        if column not in columns:
            raise ValueError(f"La columna '{column}' no existe en '{definition.table}'.")

    if definition.aggregation in {"sum", "avg"} and definition.metric:
        if _column_kind(columns[definition.metric].type) != "number":
            raise ValueError(f"'{definition.metric}' no es una métrica numérica.")

    return table, columns


def _literal(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _filter_sql(item: VisualizationFilter) -> str:
    column = _quote(item.column)
    if item.operator == "in":
        if not isinstance(item.value, list) or not item.value:
            raise ValueError("El filtro IN necesita una lista con valores.")
        return f"{column} IN ({', '.join(_literal(value) for value in item.value)})"
    if item.operator == "contains":
        return f"{column} LIKE {_literal('%' + str(item.value) + '%')}"
    operators = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
    return f"{column} {operators[item.operator]} {_literal(item.value)}"


def build_visualization_query(definition: VisualizationDefinition) -> str:
    _resolve_definition(definition)
    table = _quote(definition.table)
    metric = "*" if definition.aggregation == "count" and not definition.metric else _quote(definition.metric or "")
    expression = f"{definition.aggregation.upper()}({metric})"

    select = []
    group = ""
    order = ""
    if definition.group_by:
        dimension = _quote(definition.group_by)
        select.append(f"{dimension} AS dimension")
        group = f" GROUP BY {dimension}"
        order = " ORDER BY value DESC"
    select.append(f"{expression} AS value")

    where = ""
    if definition.filters:
        where = " WHERE " + " AND ".join(_filter_sql(item) for item in definition.filters)

    provider = database_manager.status().get("provider")
    limit = ""
    top = ""
    if definition.group_by:
        if provider == "sqlserver":
            top = f"TOP {definition.limit} "
        else:
            limit = f" LIMIT {definition.limit}"

    return f"SELECT {top}{', '.join(select)} FROM {table}{where}{group}{order}{limit};"


def preview_visualization(definition: VisualizationDefinition) -> dict:
    sql = build_visualization_query(definition)
    rows = execute_query(sql)
    return {
        "definition": definition.model_dump(),
        "data": rows,
        "meta": {
            "rows": len(rows),
            "provider": database_manager.status().get("provider"),
        },
    }

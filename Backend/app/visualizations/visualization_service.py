import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.database.database_manager import database_manager
from app.database.inspector import inspect_database
from app.database.query_executor import execute_query


VisualizationType = Literal["kpi", "bar", "line", "donut", "table"]
AggregationType = Literal["count", "sum", "avg", "min", "max"]


class VisualizationFilter(BaseModel):
    table: str | None = None
    column: str
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "contains", "in"] = "eq"
    value: str | int | float | bool | list[str | int | float]


class VisualizationDefinition(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    visualization: VisualizationType
    table: str
    metric: str | None = None
    metric_table: str | None = None
    aggregation: AggregationType = "count"
    group_by: str | None = None
    group_by_table: str | None = None
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


def _find_join_path(schema, start_table: str, target_table: str):
    if start_table == target_table:
        return []

    graph = {name: [] for name in schema.tables}
    for rel in schema.relationships:
        graph.setdefault(rel.table, []).append((rel.references_table, rel))
        graph.setdefault(rel.references_table, []).append((rel.table, rel))

    queue = [(start_table, [])]
    visited = {start_table}
    while queue:
        current, path = queue.pop(0)
        for neighbor, rel in graph.get(current, []):
            if neighbor in visited:
                continue
            next_path = path + [(current, neighbor, rel)]
            if neighbor == target_table:
                return next_path
            visited.add(neighbor)
            queue.append((neighbor, next_path))
    raise ValueError(f"No existe una relación entre '{start_table}' y '{target_table}'.")


def _resolve_definition(definition: VisualizationDefinition):
    schema = inspect_database()
    base_table = schema.tables.get(definition.table)
    if base_table is None:
        raise ValueError(f"La tabla '{definition.table}' no existe.")

    metric_table = definition.metric_table or definition.table
    group_table = definition.group_by_table or definition.table
    requested = []
    if definition.metric:
        requested.append((metric_table, definition.metric))
    if definition.group_by:
        requested.append((group_table, definition.group_by))
    requested.extend(((item.table or definition.table), item.column) for item in definition.filters)

    for table_name, column_name in requested:
        table = schema.tables.get(table_name)
        if table is None:
            raise ValueError(f"La tabla '{table_name}' no existe.")
        columns = {column.name: column for column in table.columns}
        if column_name not in columns:
            raise ValueError(f"La columna '{column_name}' no existe en '{table_name}'.")

    if definition.aggregation in {"sum", "avg"} and definition.metric:
        metric_columns = {column.name: column for column in schema.tables[metric_table].columns}
        if _column_kind(metric_columns[definition.metric].type) != "number":
            raise ValueError(f"'{definition.metric}' no es una métrica numérica.")

    target_tables = {table for table, _ in requested}
    paths = {target: _find_join_path(schema, definition.table, target) for target in target_tables if target != definition.table}
    return schema, paths


def _qualified(table: str, column: str) -> str:
    return f"{_quote(table)}.{_quote(column)}"


def _join_sql(schema, base_table: str, paths: dict) -> str:
    joins = []
    joined = {base_table}
    pending = [edge for path in paths.values() for edge in path]
    while pending:
        progressed = False
        for edge in list(pending):
            left, right, rel = edge
            if left not in joined:
                continue
            if right in joined:
                pending.remove(edge)
                progressed = True
                continue
            if rel.table == left and rel.references_table == right:
                condition = f"{_qualified(left, rel.column)} = {_qualified(right, rel.references_column)}"
            else:
                condition = f"{_qualified(left, rel.references_column)} = {_qualified(right, rel.column)}"
            joins.append(f" LEFT JOIN {_quote(right)} ON {condition}")
            joined.add(right)
            pending.remove(edge)
            progressed = True
        if not progressed:
            raise ValueError("No fue posible construir la ruta de relaciones.")
    return "".join(joins)


def _literal(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _filter_sql(item: VisualizationFilter, base_table: str) -> str:
    column = _qualified(item.table or base_table, item.column)
    if item.operator == "in":
        if not isinstance(item.value, list) or not item.value:
            raise ValueError("El filtro IN necesita una lista con valores.")
        return f"{column} IN ({', '.join(_literal(value) for value in item.value)})"
    if item.operator == "contains":
        return f"{column} LIKE {_literal('%' + str(item.value) + '%')}"
    operators = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
    return f"{column} {operators[item.operator]} {_literal(item.value)}"


def build_visualization_query(definition: VisualizationDefinition) -> str:
    schema, paths = _resolve_definition(definition)
    metric_table = definition.metric_table or definition.table
    group_table = definition.group_by_table or definition.table
    metric = "*" if definition.aggregation == "count" and not definition.metric else _qualified(metric_table, definition.metric or "")
    expression = f"{definition.aggregation.upper()}({metric})"

    select = []
    group = ""
    order = ""
    if definition.group_by:
        dimension = _qualified(group_table, definition.group_by)
        select.append(f"{dimension} AS dimension")
        group = f" GROUP BY {dimension}"
        order = " ORDER BY value DESC"
    select.append(f"{expression} AS value")

    where = ""
    if definition.filters:
        where = " WHERE " + " AND ".join(_filter_sql(item, definition.table) for item in definition.filters)

    provider = database_manager.status().get("provider")
    limit = ""
    top = ""
    if definition.group_by:
        if provider == "sqlserver":
            top = f"TOP {definition.limit} "
        else:
            limit = f" LIMIT {definition.limit}"

    joins = _join_sql(schema, definition.table, paths)
    return f"SELECT {top}{', '.join(select)} FROM {_quote(definition.table)}{joins}{where}{group}{order}{limit};"



class VisualizationPageRequest(BaseModel):
    definition: VisualizationDefinition
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
    search: str = Field(default="", max_length=100)
    sort_by: Literal["dimension", "value"] = "value"
    descending: bool = True


def explore_visualization(request: VisualizationPageRequest) -> dict:
    definition = request.definition
    if definition.visualization != "table":
        raise ValueError("La exploración está disponible para tablas.")
    sql = build_visualization_query(definition)
    provider = database_manager.status().get("provider")
    if provider == "sqlserver":
        sql = re.sub(r"^SELECT TOP \d+ ", "SELECT ", sql, count=1)
    else:
        sql = re.sub(r" LIMIT \d+;?$", "", sql)
    sql = sql.rstrip(";")
    columns = ["dimension", "value"] if definition.group_by else ["value"]
    where = ""
    if request.search and definition.group_by:
        cast_type = "NVARCHAR(4000)" if provider == "sqlserver" else "TEXT"
        escaped = request.search.replace("'", "''").replace("%", "\\%").replace("_", "\\_")
        where = f" WHERE CAST(dimension AS {cast_type}) LIKE '%{escaped}%' ESCAPE '\\'"
    source = f"({sql}) AS results"
    total = execute_query(f"SELECT COUNT(*) AS total FROM {source}{where}")[0]["total"]
    sort = request.sort_by if request.sort_by in columns else "value"
    direction = "DESC" if request.descending else "ASC"
    offset = (request.page - 1) * request.page_size
    if provider == "sqlserver":
        page_sql = f"SELECT * FROM {source}{where} ORDER BY {sort} {direction} OFFSET {offset} ROWS FETCH NEXT {request.page_size} ROWS ONLY"
    else:
        page_sql = f"SELECT * FROM {source}{where} ORDER BY {sort} {direction} LIMIT {request.page_size} OFFSET {offset}"
    return {"data": execute_query(page_sql), "total": total, "page": request.page, "page_size": request.page_size, "columns": columns}


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


def get_filter_values(table: str, column: str, search: str = "", limit: int = 50) -> dict:
    """Return bounded distinct values from a schema-validated field."""
    schema = inspect_database()
    selected = schema.tables.get(table)
    if selected is None or column not in {field.name for field in selected.columns}:
        raise ValueError("La tabla o columna seleccionada no existe.")
    if len(search) > 100:
        raise ValueError("La búsqueda es demasiado larga.")
    limit = max(1, min(limit, 100))
    field = f"{_quote(column)}"
    source = _quote(table)
    provider = database_manager.status().get("provider")
    where = f" WHERE {field} IS NOT NULL"
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        cast = f"CAST({field} AS NVARCHAR(4000))" if provider == "sqlserver" else f"CAST({field} AS TEXT)"
        where += f" AND {cast} LIKE {_literal('%' + escaped + '%')} ESCAPE {_literal(chr(92))}"
    if provider == "sqlserver":
        sql = f"SELECT DISTINCT TOP {limit} {field} AS value FROM {source}{where} ORDER BY {field}"
    else:
        sql = f"SELECT DISTINCT {field} AS value FROM {source}{where} ORDER BY {field} LIMIT {limit}"
    rows = execute_query(sql)
    return {"values": [str(row["value"]) for row in rows if row.get("value") is not None], "limit": limit}

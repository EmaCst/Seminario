import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.database.database_manager import database_manager
from app.database.inspector import inspect_database
from app.database.query_executor import execute_query


VisualizationType = Literal["kpi", "bar", "line", "area", "donut", "table"]
AggregationType = Literal["count", "distinct_count", "sum", "avg", "min", "max"]


class VisualizationColumn(BaseModel):
    table: str | None = None
    column: str


class VisualizationFilter(BaseModel):
    table: str | None = None
    value_table: str | None = None
    column: str
    operator: Literal[
        "eq", "neq", "gt", "gte", "lt", "lte", "contains", "in",
        "lt_field", "lte_field", "gt_field", "gte_field",
        "is_null", "not_null", "between",
    ] = "eq"
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
    group_by_identity: str | None = None
    sort_direction: Literal["asc", "desc"] = "desc"
    time_granularity: Literal["raw", "month", "quarter", "year"] = "raw"
    filters: list[VisualizationFilter] = Field(default_factory=list, max_length=20)
    table_mode: Literal["aggregate", "detail"] = "aggregate"
    detail_columns: list[VisualizationColumn] = Field(default_factory=list, max_length=8)
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_shape(self):
        if self.aggregation != "count" and not self.metric:
            raise ValueError("Selecciona una métrica para esta agregación.")
        if self.visualization in {"bar", "line", "area", "donut"} and not self.group_by:
            raise ValueError("Esta visualización necesita una dimensión para agrupar.")
        if self.time_granularity != "raw" and not self.group_by:
            raise ValueError("Selecciona una fecha para agrupar por mes o año.")
        if self.group_by_identity and (not self.group_by or self.time_granularity != "raw"):
            raise ValueError("La identidad solo se aplica a dimensiones no temporales.")
        if self.table_mode == "detail":
            if self.visualization != "table":
                raise ValueError("El modo de registros está disponible únicamente para tablas.")
            if not self.detail_columns:
                raise ValueError("Selecciona al menos una columna para mostrar los registros.")
        if self.visualization == "kpi" and self.group_by:
            raise ValueError("Un indicador KPI no admite agrupación por dimensión.")
        if self.aggregation == "distinct_count" and not self.metric and self.table_mode != "detail":
            raise ValueError("Selecciona la columna cuyos valores únicos deseas contar.")

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
    """Allow only unambiguous many-to-one paths from a fact to a dimension.

    Walking a parent->child relationship multiplies fact rows and silently
    corrupts SUM/COUNT/AVG for many domains. Even if two joins reach the same
    table, never choose one arbitrarily.
    """
    if start_table == target_table:
        return []

    graph = {name: [] for name in schema.tables}
    for rel in schema.relationships:
        parent = schema.tables.get(rel.references_table)
        child = schema.tables.get(rel.table)
        if not parent or not child:
            continue
        if len(parent.primary_key) != 1 or rel.references_column != parent.primary_key[0]:
            continue
        graph.setdefault(rel.table, []).append((rel.references_table, rel))

    queue = [(start_table, [])]
    seen_length = {start_table: 0}
    shortest_paths = []
    shortest = None
    while queue:
        current, path = queue.pop(0)
        if shortest is not None and len(path) >= shortest:
            continue
        for neighbor, rel in graph.get(current, []):
            if any(step[1] == neighbor for step in path) or neighbor == start_table:
                continue
            following = path + [(current, neighbor, rel)]
            if neighbor == target_table:
                shortest = len(following)
                shortest_paths.append(following)
                continue
            if len(following) >= 5:
                continue
            if len(following) <= seen_length.get(neighbor, 999):
                seen_length[neighbor] = len(following)
                queue.append((neighbor, following))
    if not shortest_paths:
        raise ValueError(
            f"No hay una relación segura de muchos-a-uno desde '{start_table}' "
            f"hacia '{target_table}'. Selecciona la tabla de hechos correcta "
            "para evitar multiplicar registros al calcular indicadores."
        )
    if len(shortest_paths) != 1:
        raise ValueError(
            f"Existen varias rutas de relación entre '{start_table}' y "
            f"'{target_table}'. Selecciona una relación inequívoca antes de calcular."
        )
    return shortest_paths[0]


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
    if definition.group_by_identity:
        requested.append((group_table, definition.group_by_identity))
        target = schema.tables.get(group_table)
        if target is None or definition.group_by_identity not in target.primary_key:
            raise ValueError("La identidad de agrupación debe ser una clave primaria verificada.")
    requested.extend(
        ((column.table or definition.table), column.column)
        for column in definition.detail_columns
    )
    requested.extend(((item.table or definition.table), item.column) for item in definition.filters)
    for item in definition.filters:
        if item.operator.endswith("_field"):
            if not isinstance(item.value, str):
                raise ValueError("La comparación de columnas requiere seleccionar una columna válida.")
            requested.append((item.value_table or item.table or definition.table, item.value))

    for table_name, column_name in requested:
        table = schema.tables.get(table_name)
        if table is None:
            raise ValueError(f"La tabla '{table_name}' no existe.")
        columns = {column.name: column for column in table.columns}
        if column_name not in columns:
            raise ValueError(f"La columna '{column_name}' no existe en '{table_name}'.")

    for item in definition.filters:
        if item.operator.endswith("_field"):
            left_table = item.table or definition.table
            right_table = item.value_table or left_table
            numeric_left = {
                col.name for col in schema.tables[left_table].columns
                if _column_kind(col.type) == "number"
            }
            numeric_right = {
                col.name for col in schema.tables[right_table].columns
                if _column_kind(col.type) == "number"
            }
            if item.column not in numeric_left or item.value not in numeric_right:
                raise ValueError(
                    "Las comparaciones requieren columnas numéricas verificables."
                )
            if left_table != right_table:
                # A dependent inventory row can safely compare with a unique
                # parent product threshold. Refuse arbitrary reverse/sideways
                # joins: those may multiply or misattribute stock.
                relation = [
                    link for link in schema.relationships
                    if link.table == left_table
                    and link.references_table == right_table
                    and link.references_column in schema.tables[right_table].primary_key
                ]
                if (left_table != definition.table or len(relation) != 1):
                    raise ValueError(
                        "La comparación entre tablas requiere una relación "
                        "única desde la tabla principal hasta la clave "
                        "primaria de la tabla de referencia."
                    )

    if definition.time_granularity != "raw":
        group_columns = {c.name: c for c in schema.tables[group_table].columns}
        group_field = group_columns[definition.group_by]
        if _column_kind(group_field.type) != "date":
            # A mapped Excel date may be represented as TEXT in SQLite.
            from app.analysis.semantic_mapper_v2 import inspect_semantic_model
            entities = (inspect_semantic_model().get("semantic_model") or {}).get("entities") or {}
            recognized_date = any(
                item.get("table") == group_table
                and not item.get("ambiguous")
                and (item.get("columns") or {}).get("date") == definition.group_by
                for item in entities.values()
            )
            if not recognized_date:
                raise ValueError("La agrupación mensual/anual requiere una columna de fecha verificable.")
    if (definition.aggregation in {"sum", "avg"}
            and definition.metric and metric_table != definition.table):
        raise ValueError(
            "No es seguro sumar o promediar importes de una tabla relacionada "
            "por cada fila de la tabla principal: se podrían duplicar valores. "
            "Selecciona como origen la entidad que contiene esa métrica."
        )
    if definition.aggregation in {"sum", "avg"} and definition.metric:
        metric_columns = {column.name: column for column in schema.tables[metric_table].columns}
        if _column_kind(metric_columns[definition.metric].type) != "number":
            raise ValueError(f"No se puede calcular {definition.aggregation} sobre '{definition.metric}' porque no es una columna numérica. Utiliza Cantidad de registros o selecciona una métrica numérica.")

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
    if item.operator.endswith("_field"):
        # Both identifiers were checked against the live DB schema. The
        # second operand is a COLUMN, never an untrusted SQL expression.
        operators = {
            "lt_field": "<", "lte_field": "<=",
            "gt_field": ">", "gte_field": ">=",
        }
        return f"{column} {operators[item.operator]} {_qualified(item.value_table or item.table or base_table, item.value)}"
    if item.operator in {"is_null", "not_null"}:
        return f"{column} IS {'NOT ' if item.operator == 'not_null' else ''}NULL"
    if item.operator == "between":
        if not isinstance(item.value, list) or len(item.value) != 2:
            raise ValueError("El filtro entre dos valores necesita un inicio y un final.")
        return f"{column} BETWEEN {_literal(item.value[0])} AND {_literal(item.value[1])}"
    if item.operator == "in":
        if not isinstance(item.value, list) or not item.value:
            raise ValueError("El filtro IN necesita una lista con valores.")
        return f"{column} IN ({', '.join(_literal(value) for value in item.value)})"
    if item.operator == "contains":
        return f"{column} LIKE {_literal('%' + str(item.value) + '%')}"
    operators = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
    return f"{column} {operators[item.operator]} {_literal(item.value)}"


def _time_bucket(expression: str, granularity: str) -> str:
    if granularity == "raw":
        return expression
    provider = database_manager.status().get("provider")
    if provider == "postgresql":
        if granularity == "quarter":
            return (f"TO_CHAR({expression}, 'YYYY') || '-Q' || "
                    f"CAST(EXTRACT(QUARTER FROM {expression}) AS TEXT)")
        fmt = "YYYY-MM" if granularity == "month" else "YYYY"
        return f"TO_CHAR({expression}, '{fmt}')"
    if provider == "sqlserver":
        if granularity == "month":
            return f"CONVERT(VARCHAR(7), {expression}, 120)"
        if granularity == "quarter":
            return f"CONCAT(YEAR({expression}), '-Q', DATEPART(QUARTER, {expression}))"
        return f"CONVERT(VARCHAR(4), {expression}, 112)"
    # Excel is imported into SQLite with ISO-formatted date values.
    if granularity == "quarter":
        return (f"strftime('%Y', {expression}) || '-Q' || "
                f"CAST(((CAST(strftime('%m', {expression}) AS INTEGER) - 1) / 3 + 1) AS INTEGER)")
    fmt = "%Y-%m" if granularity == "month" else "%Y"
    return f"strftime('{fmt}', {expression})"


def build_visualization_query(definition: VisualizationDefinition) -> str:
    schema, paths = _resolve_definition(definition)
    if definition.visualization == "table" and definition.table_mode == "detail":
        fields = [
            f"{_qualified(item.table or definition.table, item.column)} AS {_quote(f'field_{index}')}"
            for index, item in enumerate(definition.detail_columns)
        ]
        filters = [
            _filter_sql(item, definition.table) for item in definition.filters
        ]
        where = " WHERE " + " AND ".join(filters) if filters else ""
        provider = database_manager.status().get("provider")
        prefix = f"TOP {definition.limit} " if provider == "sqlserver" else ""
        ending = "" if provider == "sqlserver" else f" LIMIT {definition.limit}"
        # A user-selected column is preferred for sorting; for same values
        # the primary key makes the result deterministic on large sources.
        base_pk = schema.tables[definition.table].primary_key
        ordering = f"field_0 {definition.sort_direction.upper()}"
        if base_pk:
            ordering += ", " + ", ".join(
                _qualified(definition.table, col) + " ASC" for col in base_pk
            )
        return (
            f"SELECT {prefix}{', '.join(fields)} FROM {_quote(definition.table)}"
            f"{_join_sql(schema, definition.table, paths)}{where}"
            f" ORDER BY {ordering}{ending};"
        )
    metric_table = definition.metric_table or definition.table
    group_table = definition.group_by_table or definition.table
    metric = "*" if definition.aggregation == "count" and not definition.metric else _qualified(metric_table, definition.metric or "")
    expression = (
        f"COUNT(DISTINCT {metric})"
        if definition.aggregation == "distinct_count"
        else f"{definition.aggregation.upper()}({metric})"
    )

    select = []
    group = ""
    order = ""
    if definition.group_by:
        dimension = _time_bucket(
            _qualified(group_table, definition.group_by), definition.time_granularity
        )
        grouping = dimension
        if definition.group_by_identity:
            # Customer names can repeat. Preserve distinct primary keys and
            # display each name with its verified identity instead of merging
            # purchases from two people who happen to share a name.
            identity = _qualified(group_table, definition.group_by_identity)
            provider = database_manager.status().get("provider")
            if provider == "excel":
                dimension = (f"COALESCE(CAST({dimension} AS TEXT), 'Sin nombre')"
                             f" || ' (#' || CAST({identity} AS TEXT) || ')'")
            else:
                dimension = (f"CONCAT(COALESCE(CAST({dimension} AS VARCHAR(200)), 'Sin nombre'),"
                             f" ' (#', CAST({identity} AS VARCHAR(50)), ')')")
            grouping += f", {identity}"
        select.append(f"{dimension} AS dimension")
        group = f" GROUP BY {grouping}"
        if definition.time_granularity != "raw":
            order = " ORDER BY dimension ASC"
        else:
            direction = definition.sort_direction.upper()
            order = f" ORDER BY value {direction}, dimension ASC"
    select.append(f"{expression} AS value")

    restrictions = [
        _filter_sql(item, definition.table) for item in definition.filters
    ]
    if definition.group_by_identity and group_table != definition.table:
        # LEFT JOIN preserves orphaned foreign keys, but an orphan is not a
        # verified customer/product. Exclude it from named-entity rankings.
        restrictions.append(
            f"{_qualified(group_table, definition.group_by_identity)} IS NOT NULL"
        )
    where = " WHERE " + " AND ".join(restrictions) if restrictions else ""

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
    sql = re.sub(r" ORDER BY (?:value (?:ASC|DESC), dimension ASC|dimension ASC);?$", "", sql).rstrip(";")
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
    try:
        rows = execute_query(sql)
    except Exception as exc:
        raise ValueError(
            "No fue posible generar la vista previa con los campos seleccionados. "
            "Revisa las relaciones, los filtros y los tipos de datos. "
            f"Detalle técnico: {exc}"
        ) from exc
    columns = (
        [
            {
                "key": f"field_{index}",
                "table": column.table or definition.table,
                "column": column.column,
                "label": column.column.replace("_", " ").capitalize(),
            }
            for index, column in enumerate(definition.detail_columns)
        ]
        if definition.visualization == "table" and definition.table_mode == "detail"
        else (
            [{"key": "dimension", "label": definition.group_by.replace("_", " ").capitalize()}]
            if definition.group_by else []
        ) + [{"key": "value", "label": definition.aggregation.replace("_", " ").capitalize()}]
    )
    return {
        "definition": definition.model_dump(),
        "data": rows,
        "meta": {
            "rows": len(rows),
            "columns": columns,
            "limited": bool(definition.group_by or definition.table_mode == "detail"),
            "limit": definition.limit,
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

from __future__ import annotations

from sqlalchemy import text

from app.analysis.adaptive_dashboard_service import (
    _provider,
    _quote,
    get_adaptive_dashboard_summary,
)
from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.database.connection import get_connection
from app.database.inspector import inspect_database


NUMERIC_ROLE_KEYS = ("total", "amount", "value", "price", "quantity", "stock", "credits")
CATEGORICAL_COLUMN_TERMS = (
    "estado", "status", "metodo", "method", "tipo", "type", "nivel", "level",
    "genero", "gender", "especialidad", "specialty", "periodo", "period",
    "concepto", "category", "categoria", "marca", "brand",
)

DOMAIN_RANKING_SPECS = {
    "retail": [
        ("customers", "sales", "sum", "total", "Clientes por gasto"),
        ("products", "sales_details", "sum", "quantity", "Productos por unidades"),
    ],
    "education": [
        ("students", "grades", "avg", "value", "Estudiantes por calificación"),
        ("students", "payments", "sum", "amount", "Estudiantes por pagos"),
    ],
    "healthcare": [
        ("doctors", "appointments", "count", None, "Médicos por citas"),
        ("patients", "appointments", "count", None, "Pacientes por citas"),
    ],
    "transportation": [
        ("routes", "trips", "count", None, "Rutas por viajes"),
        ("drivers", "trips", "count", None, "Conductores por viajes"),
    ],
    "hospitality": [
        ("guests", "reservations", "count", None, "Huéspedes por reservas"),
        ("rooms", "reservations", "count", None, "Habitaciones por reservas"),
    ],
    "professional_services": [
        ("clients", "invoices", "sum", "total", "Clientes por facturación"),
        ("clients", "projects", "count", None, "Clientes por proyectos"),
    ],
    "finance_accounting": [
        ("accounts", "transactions", "sum", "amount", "Cuentas por movimiento"),
    ],
    "human_resources": [
        ("departments", "employees", "count", None, "Departamentos por empleados"),
    ],
}


def _pct_change(current: float, previous: float | None) -> float | None:
    if previous in (None, 0):
        return None
    return round(((current - previous) / previous) * 100.0, 2)


def _period_label(point: dict) -> str:
    return f"{int(point['month']):02d}/{int(point['year'])}"


def _trend_analysis(trend: dict) -> dict:
    points = trend.get("data") or []
    role = trend.get("role")

    if not trend.get("available") or not points:
        return {
            "available": False,
            "role": role,
            "data": [],
            "current": None,
            "previous": None,
            "change_absolute": None,
            "change_pct": None,
            "peak": None,
            "lowest": None,
            "average": None,
            "cumulative": 0,
            "periods": 0,
        }

    normalized = []
    running_total = 0.0
    raw_totals: list[float] = []

    for point in points:
        total = float(point.get("total") or 0)
        raw_totals.append(total)
        running_total += total
        window = raw_totals[-3:]
        normalized.append({
            **point,
            "period": _period_label(point),
            "total": total,
            "rolling_average": round(sum(window) / len(window), 2),
            "cumulative": round(running_total, 2),
        })

    current = normalized[-1]
    previous = normalized[-2] if len(normalized) > 1 else None
    peak = max(normalized, key=lambda item: item["total"])
    lowest = min(normalized, key=lambda item: item["total"])
    average = sum(raw_totals) / len(raw_totals)
    previous_total = previous["total"] if previous else None

    return {
        "available": True,
        "role": role,
        "data": normalized,
        "current": current,
        "previous": previous,
        "change_absolute": round(current["total"] - previous_total, 2) if previous_total is not None else None,
        "change_pct": _pct_change(current["total"], previous_total),
        "peak": peak,
        "lowest": lowest,
        "average": round(average, 2),
        "cumulative": round(sum(raw_totals), 2),
        "periods": len(normalized),
        "range": {
            "from": normalized[0]["period"],
            "to": normalized[-1]["period"],
        },
    }


def _numeric_summary(table: str, column: str) -> dict | None:
    qtable = _quote(table)
    qcolumn = _quote(column)
    sql = text(
        f"SELECT COUNT({qcolumn}) AS records, SUM({qcolumn}) AS total, AVG({qcolumn}) AS average, "
        f"MIN({qcolumn}) AS minimum, MAX({qcolumn}) AS maximum FROM {qtable} WHERE {qcolumn} IS NOT NULL;"
    )
    try:
        with get_connection() as connection:
            row = connection.execute(sql).mappings().first()
        if not row or row["records"] == 0:
            return None
        return {
            "records": int(row["records"]),
            "total": round(float(row["total"] or 0), 2),
            "average": round(float(row["average"] or 0), 2),
            "minimum": round(float(row["minimum"] or 0), 2),
            "maximum": round(float(row["maximum"] or 0), 2),
        }
    except Exception:
        return None


def _collect_numeric_metrics(entities: dict) -> list[dict]:
    metrics = []
    seen: set[tuple[str, str]] = set()

    for role, entity in entities.items():
        table = entity.get("table")
        columns = entity.get("columns") or {}
        if not table:
            continue
        for semantic_key in NUMERIC_ROLE_KEYS:
            column = columns.get(semantic_key)
            if not column or (table, column) in seen:
                continue
            seen.add((table, column))
            summary = _numeric_summary(table, column)
            if summary:
                metrics.append({
                    "role": role,
                    "table": table,
                    "metric": semantic_key,
                    "column": column,
                    **summary,
                })
            if len(metrics) >= 8:
                return metrics
    return metrics


def _categorical_distribution(table: str, column: str, limit: int = 8) -> list[dict]:
    qtable = _quote(table)
    qcolumn = _quote(column)
    cast_type = "VARCHAR(255)" if _provider() == "postgresql" else "NVARCHAR(255)"
    limit_clause = f"LIMIT {limit}" if _provider() == "postgresql" else ""
    top_clause = "" if _provider() == "postgresql" else f"TOP {limit} "
    sql = text(
        f"SELECT {top_clause}CAST({qcolumn} AS {cast_type}) AS label, COUNT(*) AS total "
        f"FROM {qtable} WHERE {qcolumn} IS NOT NULL "
        f"GROUP BY CAST({qcolumn} AS {cast_type}) ORDER BY total DESC {limit_clause};"
    )
    with get_connection() as connection:
        rows = connection.execute(sql).mappings().all()
    return [{"label": str(row["label"]), "total": int(row["total"])} for row in rows]


def _collect_distributions(entities: dict, primary_status: dict) -> list[dict]:
    distributions = []
    used: set[tuple[str, str]] = set()

    if primary_status.get("available"):
        role = primary_status.get("role")
        entity = entities.get(role) or {}
        status_col = (entity.get("columns") or {}).get("status")
        if status_col:
            used.add((entity.get("table"), status_col))
        distributions.append({
            "role": role,
            "column": status_col or "status",
            "label": "Estado",
            "data": primary_status.get("data") or [],
        })

    schema = inspect_database()
    for role, entity in entities.items():
        table_name = entity.get("table")
        table = schema.tables.get(table_name) if table_name else None
        if not table:
            continue

        for column in table.columns:
            normalized = column.name.lower()
            if not any(term in normalized for term in CATEGORICAL_COLUMN_TERMS):
                continue
            if (table_name, column.name) in used:
                continue
            try:
                data = _categorical_distribution(table_name, column.name)
            except Exception:
                continue
            if 2 <= len(data) <= 8:
                distributions.append({
                    "role": role,
                    "column": column.name,
                    "label": column.name.replace("_", " ").title(),
                    "data": data,
                })
                used.add((table_name, column.name))
            if len(distributions) >= 4:
                return distributions
    return distributions


def _direct_relationship(left_table: str, right_table: str):
    schema = inspect_database()
    for rel in schema.relationships:
        if rel.table == left_table and rel.references_table == right_table:
            return {
                "left_column": rel.column,
                "right_column": rel.references_column,
            }
        if rel.table == right_table and rel.references_table == left_table:
            return {
                "left_column": rel.references_column,
                "right_column": rel.column,
            }
    return None


def _ranking_query(target: dict, metric: dict, aggregate: str, metric_key: str | None, title: str) -> dict | None:
    target_table = target.get("table")
    metric_table = metric.get("table")
    target_columns = target.get("columns") or {}
    metric_columns = metric.get("columns") or {}
    name_column = target_columns.get("name")
    if not target_table or not metric_table or not name_column:
        return None

    relation = _direct_relationship(metric_table, target_table)
    if not relation:
        return None

    qmetric = _quote(metric_table)
    qtarget = _quote(target_table)
    qname = _quote(name_column)
    left_fk = _quote(relation["left_column"])
    right_pk = _quote(relation["right_column"])

    if aggregate == "count":
        metric_expr = "COUNT(*)"
    else:
        metric_column = metric_columns.get(metric_key or "")
        if not metric_column:
            return None
        metric_expr = f"{aggregate.upper()}(m.{_quote(metric_column)})"

    top_clause = "TOP 5 " if _provider() != "postgresql" else ""
    limit_clause = "LIMIT 5" if _provider() == "postgresql" else ""
    sql = text(
        f"SELECT {top_clause}t.{qname} AS label, {metric_expr} AS value "
        f"FROM {qmetric} m JOIN {qtarget} t ON m.{left_fk} = t.{right_pk} "
        f"GROUP BY t.{qname} ORDER BY value DESC {limit_clause};"
    )

    try:
        with get_connection() as connection:
            rows = connection.execute(sql).mappings().all()
    except Exception:
        return None

    if not rows:
        return None
    return {
        "title": title,
        "target_role": next((role for role, value in (inspect_semantic_model().get("semantic_model") or {}).get("entities", {}).items() if value.get("table") == target_table), None),
        "metric_role": next((role for role, value in (inspect_semantic_model().get("semantic_model") or {}).get("entities", {}).items() if value.get("table") == metric_table), None),
        "aggregate": aggregate,
        "data": [
            {"label": str(row["label"]), "value": round(float(row["value"] or 0), 2)}
            for row in rows
        ],
    }


def _build_rankings(domain: str | None, entities: dict) -> list[dict]:
    rankings = []
    for target_role, metric_role, aggregate, metric_key, title in DOMAIN_RANKING_SPECS.get(domain, []):
        target = entities.get(target_role)
        metric = entities.get(metric_role)
        if not target or not metric:
            continue
        result = _ranking_query(target, metric, aggregate, metric_key, title)
        if result:
            rankings.append(result)
    return rankings[:3]


def _build_insights(trend: dict, distributions: list[dict], entity_counts: list[dict], rankings: list[dict]) -> list[dict]:
    insights: list[dict] = []

    if trend.get("available"):
        current = trend.get("current") or {}
        previous = trend.get("previous") or {}
        change_pct = trend.get("change_pct")
        peak = trend.get("peak") or {}
        lowest = trend.get("lowest") or {}
        average = trend.get("average")

        if change_pct is not None:
            direction = "aumentó" if change_pct >= 0 else "disminuyó"
            insights.append({
                "type": "trend",
                "title": "Cambio frente al período anterior",
                "text": f"{trend.get('role')} {direction} {abs(change_pct):.1f}% en {current.get('period')} frente a {previous.get('period')}.",
            })

        if peak and average not in (None, 0):
            above_average = _pct_change(float(peak.get("total") or 0), float(average))
            insights.append({
                "type": "peak",
                "title": "Mejor período",
                "text": f"{peak.get('period')} registró {peak.get('total'):g}, {abs(above_average or 0):.1f}% por encima del promedio histórico.",
            })

        if lowest:
            insights.append({
                "type": "low",
                "title": "Período de menor actividad",
                "text": f"El menor nivel observado fue {lowest.get('period')} con {lowest.get('total'):g} registros.",
            })

    if distributions:
        first = distributions[0]
        values = first.get("data") or []
        if values:
            leader = values[0]
            total = sum(float(item.get("total") or 0) for item in values)
            share = float(leader.get("total") or 0) / total * 100 if total else 0
            insights.append({
                "type": "distribution",
                "title": "Categoría predominante",
                "text": f"{leader.get('label')} concentra {share:.1f}% de la distribución {first.get('label', '').lower()} en {first.get('role')}.",
            })

    if rankings:
        top = rankings[0]
        rows = top.get("data") or []
        if rows:
            insights.append({
                "type": "ranking",
                "title": "Líder del ranking",
                "text": f"{rows[0]['label']} encabeza “{top.get('title')}” con {rows[0]['value']:g}.",
            })

    if entity_counts:
        largest = max(entity_counts, key=lambda item: item.get("value") or 0)
        insights.append({
            "type": "coverage",
            "title": "Entidad con mayor volumen",
            "text": f"{largest.get('role')} es la entidad mapeada con más registros: {largest.get('value', 0)}.",
        })

    return insights[:6]


def get_adaptive_analytics() -> dict:
    dashboard = get_adaptive_dashboard_summary()
    analysis = inspect_semantic_model()
    semantic = analysis.get("semantic_model") or {}
    entities = semantic.get("entities") or {}

    trend = _trend_analysis(dashboard.get("trend") or {})
    status_distribution = dashboard.get("status_distribution") or {"available": False, "role": None, "data": []}
    entity_counts = dashboard.get("entity_counts") or []
    numeric_metrics = _collect_numeric_metrics(entities)
    distributions = _collect_distributions(entities, status_distribution)
    rankings = _build_rankings(dashboard.get("domain"), entities)

    return {
        "database": dashboard.get("database"),
        "provider": dashboard.get("provider"),
        "domain": dashboard.get("domain"),
        "domain_confidence": dashboard.get("domain_confidence"),
        "trend": trend,
        "status_distribution": status_distribution,
        "entity_counts": entity_counts,
        "numeric_metrics": numeric_metrics,
        "distributions": distributions,
        "rankings": rankings,
        "metadata": {
            "entities_detected": len(entities),
            "relations_detected": dashboard.get("relations_detected", 0),
            "unmapped_tables": len(dashboard.get("unmapped_tables") or []),
            "periods_analyzed": trend.get("periods", 0),
            "date_range": trend.get("range"),
        },
        "insights": _build_insights(trend, distributions, entity_counts, rankings),
    }

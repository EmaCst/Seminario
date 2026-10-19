"""Evidence-based anomaly investigation for every mapped business domain.

No arbitrary LLM SQL and no unsupported JOINs. Only group-by columns explicitly
validated by Kenneth's semantic model are queried on the selected entity.
The result is a descriptive contribution breakdown, never a causal claim.
"""
from __future__ import annotations

from sqlalchemy import text

from app.analysis.adaptive_dashboard_service import _provider, _quote
from app.database.connection import get_connection
from app.services.assistant_analytics import _month_expr, _year_expr
from app.services.assistant_domain_analytics import _measure


# Categorical, non-identifying fields; avoid patient, employee, customer and
# free-text columns that could disclose sensitive personal information.
DIMENSIONS = ("status", "type", "method", "origin", "destination")
MAX_GROUPS = 40


def _monthly_groups(
    entity: dict, dimension: str, year: int, month: int, metric: str,
    domain: str, role: str,
) -> dict[str, float] | None:
    columns = entity.get("columns") or {}
    date = columns.get("date")
    category = columns.get(dimension)
    if not date or not category or not entity.get("table") or entity.get("ambiguous"):
        return None
    expression = _measure(domain, role, entity, metric)
    if not expression:
        return None
    qdate = f"t.{_quote(date)}"
    qcat = f"t.{_quote(category)}"
    # Return NULL in the comparison too, otherwise component totals do not add up.
    rendered = f"CAST({qcat} AS {'NVARCHAR(255)' if _provider() == 'sqlserver' else 'VARCHAR(255)'})"
    limit = f"TOP {MAX_GROUPS + 1} " if _provider() == "sqlserver" else ""
    suffix = "" if _provider() == "sqlserver" else f" LIMIT {MAX_GROUPS + 1}"
    statement = (
        f"SELECT {limit}{rendered} AS label, {expression} AS total "
        f"FROM {_quote(entity['table'])} t "
        f"WHERE {_year_expr(qdate)} = :year AND {_month_expr(qdate)} = :month "
        f"GROUP BY {qcat} ORDER BY total DESC{suffix}"
    )
    with get_connection() as connection:
        rows = connection.execute(text(statement), {"year": year, "month": month}).mappings().all()
    if len(rows) > MAX_GROUPS:
        return None  # Truncated groups would create fictitious contributions.
    return {str(row["label"]) if row["label"] is not None else "(sin dato)":
            float(row["total"] or 0) for row in rows}


def explain_deviations(
    anomalies: list[dict], historical: list[dict], *,
    domain: str, role: str, entity: dict, metric: str,
    max_periods: int = 5,
) -> dict:
    """Compare anomalous periods with the same month a year earlier, or prior month.

    'Contributors' are observed segment differences, not explanations for the
    statistical seasonal residual itself and not verified root causes.
    """
    known = {(int(p["year"]), int(p["month"])) for p in historical}
    investigations = []
    dimensions = [key for key in DIMENSIONS if (entity.get("columns") or {}).get(key)][:3]
    for point in sorted(anomalies, key=lambda item: abs(float(item.get("deviation") or 0)),
                        reverse=True)[:max_periods]:
        year, month = int(point["year"]), int(point["month"])
        previous_year = (year - 1, month)
        previous_month = (year - 1, 12) if month == 1 else (year, month - 1)
        reference = previous_year if previous_year in known else (
            previous_month if previous_month in known else None
        )
        finding = {
            "year": year, "month": month,
            "reference_period": {"year": reference[0], "month": reference[1]}
                                if reference else None,
            "reference_type": ("same_month_previous_year"
                               if reference == previous_year else "previous_month")
                              if reference else None,
            "contributors": [], "limitations": [],
            "causality": "not_established",
        }
        if reference is None:
            finding["limitations"].append("No hay un período anterior verificable para comparar segmentos.")
        for dimension in dimensions if reference else []:
            try:
                current = _monthly_groups(entity, dimension, year, month, metric, domain, role)
                earlier = _monthly_groups(entity, dimension, reference[0], reference[1],
                                          metric, domain, role)
            except Exception:
                finding["limitations"].append(
                    f"No fue posible consultar el desglose por {dimension}.")
                continue
            if current is None or earlier is None:
                finding["limitations"].append(
                    f"Se omitió {dimension}: columna no disponible o cardinalidad excesiva.")
                continue
            deltas = [
                {"dimension": dimension, "category": label,
                 "current": round(current.get(label, 0), 2),
                 "reference": round(earlier.get(label, 0), 2),
                 "change": round(current.get(label, 0) - earlier.get(label, 0), 2)}
                for label in sorted(set(current) | set(earlier))
            ]
            deltas.sort(key=lambda item: abs(item["change"]), reverse=True)
            finding["contributors"].extend(deltas[:3])
        if not finding["contributors"]:
            finding["limitations"].append(
                "El modelo semántico no identificó desgloses categóricos verificables "
                "en la tabla temporal seleccionada.")
        finding["contributors"].sort(key=lambda item: abs(item["change"]), reverse=True)
        finding["contributors"] = finding["contributors"][:6]
        investigations.append(finding)
    return {
        "method": "verified_single_entity_period_comparison",
        "domain": domain, "role": role,
        "metric": metric, "investigated": len(investigations),
        "investigations": investigations,
        "warning": (
            "Los cambios por segmento son asociaciones descriptivas frente a un período "
            "de referencia; no demuestran causas ni explican automáticamente el "
            "residuo respecto al pronóstico estacional."
        ),
    }

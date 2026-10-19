from __future__ import annotations

from dataclasses import dataclass
from app.ml.seasonal_forecasting import forecast_monthly
from app.ml.anomaly_detection import detect_anomalies
from app.ml.diagnostic_service import explain_deviations

from app.analysis.adaptive_dashboard_service import _monthly_count, DOMAIN_TREND_PRIORITY
from app.services.assistant_domain_analytics import (
    ROLE_WORDS, ROLE_LABELS, _matched_role, _measure, _query_series,
)
from app.services.assistant_router import normalize
from app.analysis.semantic_mapper_v2 import inspect_semantic_model


@dataclass
class TimeSeriesCandidate:
    role: str
    table: str
    date_column: str
    data: list[dict]
    metric: str = "count"
    domain: str = ""
    entity: dict | None = None


def _find_best_time_series(
    question: str = "", *, minimum_points: int = 3,
) -> TimeSeriesCandidate:
    """Select the requested entity, never an unrelated longer time series."""
    analysis = inspect_semantic_model()
    semantic = analysis.get("semantic_model") or {}
    domain = semantic.get("domain")
    if semantic.get("ambiguous_domain") or domain is None:
        raise ValueError("El dominio de la base es ambiguo; no puedo seleccionar una serie temporal confiable.")
    entities = semantic.get("entities") or {}
    normalized = normalize(question)
    requested_role = _matched_role(normalized, domain) if question else None
    if question and not requested_role:
        # Mention of an entity from another domain must never pick an
        # unrelated default time series (e.g. "citas" in an HR database).
        foreign = [role for other_domain in ROLE_WORDS if other_domain != domain
                   for role in [_matched_role(normalized, other_domain)] if role]
        if foreign:
            raise ValueError(
                "La entidad solicitada no está identificada de forma única en "
                "el dominio activo. Especifica qué indicador deseas analizar."
            )
    if requested_role and requested_role not in entities:
        raise ValueError(f"No encontré una tabla de {ROLE_LABELS.get(requested_role, requested_role)} identificada con suficiente certeza.")

    preferred = DOMAIN_TREND_PRIORITY.get(domain, [])
    ordered = ([requested_role] if requested_role else
               [name for name in preferred if name in entities] +
               [name for name in entities if name not in preferred])

    requested_amount = any(term in normalized for term in (
        "importe", "monto", "dinero", "ingreso", "facturacion", "recaudacion",
        "valor total", "gasto", "nomina", "salario",
    ))
    # For explicit sales forecasts, prefer recorded revenue, but only when
    # the user has not explicitly requested a count of transactions.
    explicit_count = any(term in normalized for term in (
        "cuantos", "cuantas", "numero de", "cantidad de", "transacciones"))
    if explicit_count:
        requested_amount = False
    elif requested_role == "sales" and "venta" in normalized:
        requested_amount = True

    candidates = []
    for role in ordered:
        entity = entities.get(role) or {}
        if entity.get("ambiguous"):
            continue
        table = entity.get("table")
        date = (entity.get("columns") or {}).get("date")
        if not table or not date:
            continue
        try:
            if requested_amount:
                expression = _measure(domain, role, entity, "amount")
                if expression is None:
                    continue
                data = _query_series(entity, expression)
                metric = "amount"
            else:
                data = _monthly_count(table, date)
                metric = "count"
        except Exception:
            continue
        if data:
            candidates.append(TimeSeriesCandidate(role, table, date, data, metric, domain, entity))
            if requested_role and len(data) >= minimum_points:
                break

    adequate = [candidate for candidate in candidates if len(candidate.data) >= minimum_points]
    if adequate:
        # Honor the domain's preferred temporal entity, not whichever table
        # happens to have the most historic rows.
        return adequate[0]
    if requested_role:
        raise ValueError(
            f"No hay al menos {minimum_points} meses de datos verificables para "
            f"{ROLE_LABELS.get(requested_role, requested_role)} con la métrica solicitada."
        )
    if requested_amount:
        raise ValueError(
            "No se encontró una serie mensual de importes monetarios verificables "
            "para la predicción o el análisis de anomalías."
        )
    raise ValueError(
        f"No encontré una serie temporal confiable con al menos {minimum_points} meses "
        "en el dominio actual."
    )


def forecast_next_months(horizon: int = 3, question: str = "") -> dict:
    if horizon < 1 or horizon > 12:
        raise ValueError("El horizonte debe estar entre 1 y 12 meses.")

    series = _find_best_time_series(question, minimum_points=3)
    points = series.data

    if len(points) < 3:
        raise ValueError(
            f"La serie temporal más completa ({series.role}) solo tiene {len(points)} mes(es). "
            "Se requieren al menos 3 meses para generar una predicción básica."
        )

    prediction = forecast_monthly(
        points, horizon,
        nonnegative=not (series.domain == "finance_accounting" and series.metric == "amount"),
    )
    return {
        **prediction,
        "role": series.role,
        "metric": series.metric,
        "table": series.table,
        "date_column": series.date_column,
        "training_points": points,
        "training_months": len(points),
    }


def detect_monthly_anomalies(question: str = "") -> dict:
    """Detect contextual anomalies and inspect verified business dimensions."""
    series = _find_best_time_series(question, minimum_points=4)
    result = detect_anomalies(
        series.data,
        nonnegative=not (series.domain == "finance_accounting" and series.metric == "amount"),
    )
    related_entities = {}
    if result["anomalies"]:
        related_entities = (inspect_semantic_model().get("semantic_model") or {}).get("entities") or {}
    diagnostics = explain_deviations(
        result["anomalies"], series.data,
        domain=series.domain, role=series.role,
        entity=series.entity or {}, metric=series.metric,
        related_entities=related_entities,
    )
    return {
        **result,
        "role": series.role, "metric": series.metric,
        "table": series.table, "date_column": series.date_column,
        "diagnostics": diagnostics,
    }

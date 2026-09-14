from __future__ import annotations

from app.analysis.adaptive_dashboard_service import get_adaptive_dashboard_summary


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
            "average": None,
        }

    normalized = [
        {
            **point,
            "period": _period_label(point),
            "total": float(point.get("total") or 0),
        }
        for point in points
    ]

    current = normalized[-1]
    previous = normalized[-2] if len(normalized) > 1 else None
    peak = max(normalized, key=lambda item: item["total"])
    average = sum(item["total"] for item in normalized) / len(normalized)

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
        "average": round(average, 2),
    }


def _build_insights(domain: str | None, trend: dict, status_distribution: dict, entity_counts: list[dict]) -> list[dict]:
    insights: list[dict] = []

    if trend.get("available"):
        current = trend.get("current") or {}
        previous = trend.get("previous") or {}
        change_pct = trend.get("change_pct")
        peak = trend.get("peak") or {}

        if change_pct is not None:
            direction = "aumentó" if change_pct >= 0 else "disminuyó"
            insights.append({
                "type": "trend",
                "title": "Cambio frente al período anterior",
                "text": (
                    f"{trend.get('role')} {direction} {abs(change_pct):.1f}% en {current.get('period')} "
                    f"frente a {previous.get('period')}."
                ),
            })

        if peak:
            insights.append({
                "type": "peak",
                "title": "Pico histórico visible",
                "text": (
                    f"El período con mayor actividad de {trend.get('role')} fue {peak.get('period')} "
                    f"con {peak.get('total'):g}."
                ),
            })

    status_data = status_distribution.get("data") or []
    if status_distribution.get("available") and status_data:
        leader = status_data[0]
        total = sum(float(item.get("total") or 0) for item in status_data)
        share = (float(leader.get("total") or 0) / total * 100.0) if total else 0.0
        insights.append({
            "type": "distribution",
            "title": "Estado predominante",
            "text": (
                f"{leader.get('label')} concentra {share:.1f}% de los registros clasificados "
                f"en {status_distribution.get('role')}."
            ),
        })

    if entity_counts:
        largest = max(entity_counts, key=lambda item: item.get("value") or 0)
        insights.append({
            "type": "coverage",
            "title": "Entidad con mayor volumen",
            "text": (
                f"{largest.get('role')} es la entidad mapeada con más registros: "
                f"{largest.get('value', 0)}."
            ),
        })

    return insights[:4]


def get_adaptive_analytics() -> dict:
    dashboard = get_adaptive_dashboard_summary()
    trend = _trend_analysis(dashboard.get("trend") or {})
    status_distribution = dashboard.get("status_distribution") or {
        "available": False,
        "role": None,
        "data": [],
    }
    entity_counts = dashboard.get("entity_counts") or []

    return {
        "database": dashboard.get("database"),
        "provider": dashboard.get("provider"),
        "domain": dashboard.get("domain"),
        "domain_confidence": dashboard.get("domain_confidence"),
        "trend": trend,
        "status_distribution": status_distribution,
        "entity_counts": entity_counts,
        "insights": _build_insights(
            dashboard.get("domain"),
            trend,
            status_distribution,
            entity_counts,
        ),
    }

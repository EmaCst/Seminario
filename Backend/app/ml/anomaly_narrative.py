"""Readable, evidence-bounded explanations for monthly business anomalies.

This is deterministic narration of observed numbers and verified comparison
breakdowns. It does not generate or imply a proven root cause.
"""
from __future__ import annotations

from app.services.assistant_domain_analytics import ROLE_LABELS


MONTH_NAMES = (
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
DIMENSION_LABELS = {
    "status": "estado",
    "type": "tipo",
    "method": "método",
    "origin": "origen",
    "destination": "destino",
}
def _metric_phrase(metric: str, value: float) -> str:
    formatted = _num(value)
    if metric == "amount":
        return f"un importe total de {formatted}"
    if metric == "average":
        return f"un promedio de {formatted}"
    if metric == "quantity":
        return f"{formatted} unidades"
    if metric == "count":
        return f"{formatted} registros"
    return f"un valor de {formatted}"


def _period(year: int, month: int) -> str:
    return f"{MONTH_NAMES[month]} de {year}"


def _num(number: float) -> str:
    """Consistent display without suggesting precision beyond two decimals."""
    value = round(float(number), 2)
    return f"{value:,.2f}"


def narrate_monthly_anomaly(
    point: dict, metric: str, investigation: dict | None = None,
) -> dict:
    """Return a plain-language explanation and diagnostic evidence.

    The anomaly is monthly; never claim an exact event day. The reference
    comparison and seasonal expectation are distinct statistical quantities.
    """
    year, month = int(point["year"]), int(point["month"])
    label = _period(year, month)
    value = float(point["total"])
    expected = point.get("expected_total")
    deviation = point.get("deviation")
    if deviation is None and expected is not None:
        deviation = value - float(expected)
    direction = "por encima" if deviation is not None and deviation > 0 else "por debajo"
    if expected is None or deviation is None:
        description = (
            f"En {label} se observó {_metric_phrase(metric, value)}. "
            "El análisis identificó un comportamiento inusual, pero no dispone "
            "de una referencia esperada verificable para cuantificarlo."
        )
    else:
        pct = point.get("pct_vs_expected")
        comparison = (
            f", equivalente a {abs(float(pct)):.1f}% de diferencia"
            if pct is not None else ""
        )
        description = (
            f"En {label} el indicador alcanzó {_metric_phrase(metric, value)}. "
            f"Según el historial, su referencia estimada era "
            f"{_metric_phrase(metric, expected)}. "
            f"El valor quedó {_num(abs(deviation))} {direction} de ese nivel"
            f"{comparison}. "
        )
        if point.get("expected_basis") == "annual_calendar_median":
            description += (
                "La comparación ya considera la tendencia y las variaciones "
                "que suelen repetirse en este mes de otros años."
            )
        else:
            description += (
                "La referencia considera la tendencia histórica, pero todavía "
                "no se ha verificado un patrón anual suficientemente completo."
            )

    facts = []
    reference = (investigation or {}).get("reference_period")
    if reference:
        ref_label = _period(int(reference["year"]), int(reference["month"]))
        reference_type = (investigation or {}).get("reference_type")
        if reference_type == "same_month_previous_year":
            facts.append(f"Al compararlo con {ref_label},")
        else:
            facts.append(f"Al compararlo con el período anterior ({ref_label}),")

        contributors = (investigation or {}).get("contributors") or []
        if contributors:
            primary = max(contributors, key=lambda row: abs(float(row.get("change") or 0)))
            key = DIMENSION_LABELS.get(primary.get("dimension"), "categoría")
            category = str(primary.get("category", "(sin dato)"))
            change = float(primary.get("change") or 0)
            movement = "aumentó" if change > 0 else "disminuyó" if change < 0 else "se mantuvo"
            facts.append(
                f"la categoría «{category}» del campo {key} {movement}: "
                f"pasó de {_metric_phrase(metric, primary.get('reference') or 0)} "
                f"a {_metric_phrase(metric, primary.get('current') or 0)}."
            )
        else:
            facts.append("no se obtuvo un desglose verificable de la variable principal.")

        related = (investigation or {}).get("related_indicators") or []
        if related:
            related_item = related[0]
            role = ROLE_LABELS.get(related_item.get("role"), str(related_item.get("role")))
            change = float(related_item.get("change") or 0)
            direction_related = "más" if change > 0 else "menos" if change < 0 else "el mismo número de"
            facts.append(
                f"En el mismo intervalo también se observaron "
                f"{_num(abs(change))} registros {direction_related} de {role}."
            )

    if facts:
        diagnostic = " ".join(facts) + (
            " Son cambios observados que orientan la investigación, "
            "pero no demuestran la causa de la anomalía."
        )
    else:
        diagnostic = (
            "No se identificaron desgloses ni indicadores comparables suficientes "
            "para explicar qué factores acompañaron este cambio. "
            "No sería correcto atribuirle una causa sin más datos."
        )
    recommendation = (
        "Conviene revisar los registros del período indicado y contrastarlos "
        "con operaciones, cambios de proceso o eventos documentados; "
        "solo así puede evaluarse una causa concreta."
    )
    return {
        "period_label": label,
        "period_iso": f"{year:04d}-{month:02d}",
        "period_granularity": "month",
        "explanation": description,
        "diagnostic_explanation": diagnostic,
        "recommendation": recommendation,
    }

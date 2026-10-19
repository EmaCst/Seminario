"""Robust, calendar-aware *retrospective* monthly anomaly detection.

Fits a median annual trend and median calendar-month effects. This is not a
causal detector: its predictions use the full observed historical sample and
must not be described as out-of-sample forecasting performance.
"""
from __future__ import annotations

from math import isfinite
from statistics import mean, median, pstdev

from app.ml.seasonal_forecasting import _validated


def _median_absolute_deviation(values: list[float]) -> float:
    if not values:
        return 0.0
    center = median(values)
    return median([abs(item - center) for item in values])


def _slope(values: list[float], dates: list[int], annual: bool) -> float:
    pairs = []
    if annual:
        indexed = dict(zip(dates, values))
        pairs = [(value - indexed[date - 12]) / 12
                 for date, value in zip(dates, values) if date - 12 in indexed]
    if not pairs:
        pairs = [(b - a) / (db - da)
                 for a, b, da, db in zip(values, values[1:], dates, dates[1:])]
    return median(pairs) if pairs else 0.0


def detect_anomalies(points: list[dict], *, nonnegative: bool = True) -> dict:
    if len(points) < 4:
        raise ValueError("Se requieren al menos 4 meses para buscar anomalías.")
    values, dates, months, gaps = _validated(points)
    contiguous = all(gap == 0 for gap in gaps)
    annual = len(values) >= 24 and contiguous
    slope = _slope(values, dates, annual)
    origin = dates[0]
    intercept = median([value - slope * (date - origin)
                        for value, date in zip(values, dates)])
    groups = {month: [] for month in range(1, 13)}
    for month, date, value in zip(months, dates, values):
        groups[month].append(value - intercept - slope * (date - origin))
    effects = {month: (median(group) if len(group) >= 2 else 0.0)
               for month, group in groups.items()} if annual else {month: 0.0 for month in groups}

    expected = [max(0.0, intercept + slope * (date - origin) + effects[month]) if nonnegative
                else intercept + slope * (date - origin) + effects[month]
                for date, month in zip(dates, months)]
    residuals = [value - fitted for value, fitted in zip(values, expected)]
    dispersion = 1.4826 * _median_absolute_deviation(residuals)
    center = median(values)
    threshold_floor = max(1.0, abs(center) * (0.12 if annual else 0.25))
    threshold = max(3.5 * dispersion, threshold_floor)

    baseline = {"average": round(mean(values), 2), "median": round(center, 2),
                "std_dev": round(pstdev(values), 2),
                "residual_mad_scale": round(dispersion, 2),
                "deviation_threshold": round(threshold, 2),
                "annual_pattern_evaluated": annual}
    items = []
    anomalies = []
    for index, (point, value, fitted, residual) in enumerate(zip(points, values, expected, residuals)):
        previous = values[index - 1] if index else None
        following = values[index + 1] if index < len(values) - 1 else None
        neighbors = [item for item in (previous, following) if item is not None]
        neighbor_mean = mean(neighbors) if neighbors else None
        pct_average = _percent_change(value, baseline["average"])
        pct_previous = _percent_change(value, previous)
        pct_neighbors = _percent_change(value, neighbor_mean)
        pct_expected = _percent_change(value, fitted)
        # Require both a material absolute and relative departure to avoid
        # flagging small noisy fluctuations in high-volume business data.
        anomaly = abs(residual) > threshold and (
            abs(pct_expected or 0.0) >= 20 or fitted == 0 and abs(residual) > threshold
        )
        ratio = abs(residual) / threshold if threshold else 0
        severity = ("alta" if ratio >= 2 else "media" if ratio >= 1.3 else "baja") if anomaly else None
        sign = "superó" if residual > 0 else "quedó por debajo de"
        percentage_phrase = (
            f"{abs(pct_expected):.1f}% respecto al esperado"
            if pct_expected is not None
            else "sin porcentaje calculable porque la referencia es cero"
        )
        reason = (
            f"El registro {value:g} {sign} su valor esperado de {fitted:.2f} "
            f"para este período; desviación de {abs(residual):.2f} "
            f"({percentage_phrase}). "
            + ("Se ajustó por patrones que reaparecen en el mismo mes de distintos años."
               if annual else
               "No hay historial anual suficiente para ajustar patrones estacionales.")
        ) if anomaly else None
        item = {
            **point, "anomaly": anomaly,
            "anomaly_score": round(ratio, 4),
            "severity": severity, "direction": "spike" if residual >= 0 else "drop",
            "series_average": baseline["average"], "series_median": baseline["median"],
            "series_std_dev": baseline["std_dev"],
            "z_score": round((value - baseline["average"]) / baseline["std_dev"], 3)
                       if baseline["std_dev"] else None,
            "previous_total": previous, "next_total": following,
            "neighbor_average": round(neighbor_mean, 2) if neighbor_mean is not None else None,
            "pct_vs_average": pct_average, "pct_vs_previous": pct_previous,
            "pct_vs_neighbors": pct_neighbors,
            "expected_total": round(fitted, 2),
            "deviation": round(residual, 2),
            "pct_vs_expected": pct_expected,
            "expected_basis": "annual_calendar_median" if annual else "robust_trend",
            "reason": reason,
        }
        items.append(item)
        if anomaly:
            anomalies.append(item)

    # Reviewable, non-alert observations keep the empty state informative.
    # They are ranked by distance from the seasonal/trend-adjusted expectation.
    # These are NOT reclassified as anomalies just to populate the UI.
    ranked = sorted(items, key=lambda item: abs(float(item["deviation"])), reverse=True)
    review_points = [
        {**point, "classification": "expected_variation"}
        for point in ranked[:min(3, len(ranked))]
    ]
    # A concrete explanation of the threshold used for the main anomaly
    # decision. Both the deviation threshold and 20% relative difference
    # must be surpassed (except when the reference is zero).
    screening = {
        "absolute_threshold": round(threshold, 2),
        "relative_threshold_pct": 20.0,
        "rule": "absolute_and_relative",
        "seasonality_adjusted": annual,
        "flagged": len(anomalies),
        "reviewed": len(review_points),
    }

    warnings = []
    if not annual:
        warnings.append(
            "Sin 24 meses consecutivos no es posible distinguir confiablemente "
            "picos anuales recurrentes de comportamientos atípicos."
        )
    if gaps and any(gaps):
        warnings.append(f"Hay {sum(gaps)} meses sin registros; no se completaron con ceros.")
    warnings.append(
        "Detección retrospectiva con umbrales robustos; es una señal estadística, "
        "no una prueba de causalidad ni un diagnóstico concluyente."
    )
    patterns = []
    if annual:
        material = max(abs(center) * 0.05, 0.01)
        for month in range(1, 13):
            if len(groups[month]) >= 2 and abs(effects[month]) >= material:
                patterns.append({
                    "month": month,
                    "direction": "increase" if effects[month] > 0 else "decrease",
                    "estimated_effect": round(effects[month], 2),
                    "observations": len(groups[month]),
                })
    return {
        "model": "robust_seasonal_residual" if annual else "robust_trend_residual",
        "months_evaluated": len(values), "baseline": baseline,
        "anomalies": anomalies, "series": items,
        "review_points": review_points, "screening": screening,
        "seasonal_patterns": patterns,
        "data_quality": {"observed_months": len(values),
                         "missing_months": sum(gaps), "continuous": contiguous},
        "warnings": warnings, "warning": " ".join(warnings),
    }


def _percent_change(value: float, reference: float | None) -> float | None:
    if reference is None or reference == 0:
        return None
    return round(100 * (value - reference) / abs(reference), 2)

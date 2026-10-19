"""Seasonal monthly forecasting with time-ordered validation.

Never select a seasonal model using in-sample fit. Monthly effects are learned
only from past observations; missing months disable seasonal fitting rather than
silently treating missing data as zero sales.
"""
from __future__ import annotations

from math import sqrt
from statistics import mean
from sklearn.linear_model import LinearRegression


def _consecutive(points: list[dict]) -> bool:
    dates = [int(p["year"]) * 12 + int(p["month"]) for p in points]
    return all(b - a == 1 for a, b in zip(dates, dates[1:]))


def _fit(values: list[float], months: list[int], seasonal: bool):
    x = [[i] for i in range(len(values))]
    trend = LinearRegression().fit(x, values)
    effects = {month: 0.0 for month in range(1, 13)}
    if seasonal:
        residuals = [value - float(trend.predict([[i]])[0])
                     for i, value in enumerate(values)]
        for month in range(1, 13):
            matching = [residuals[i] for i, m in enumerate(months) if m == month]
            if len(matching) >= 2:
                # Shrink small historical samples towards no seasonal effect.
                effects[month] = mean(matching) * len(matching) / (len(matching) + 1)
        # Center the seasonal effects so they do not change the annual level.
        offset = mean(effects.values())
        effects = {month: value - offset for month, value in effects.items()}

    def predict(index: int, month: int) -> float:
        return max(0.0, float(trend.predict([[index]])[0]) + effects[month])

    return predict, effects


def _metrics(actual: list[float], predicted: list[float]) -> dict:
    errors = [abs(a - p) for a, p in zip(actual, predicted)]
    mae = mean(errors)
    rmse = sqrt(mean([(a - p) ** 2 for a, p in zip(actual, predicted)]))
    average = mean(actual)
    denominator = sum((a - average) ** 2 for a in actual)
    r2 = 1 - sum((a - p) ** 2 for a, p in zip(actual, predicted)) / denominator if denominator > 0 else None
    wape = 100 * sum(errors) / sum(abs(a) for a in actual) if any(actual) else None
    return {"mae": round(mae, 2), "rmse": round(rmse, 2),
            "r2": round(r2, 4) if r2 is not None else None,
            "wape": round(wape, 2) if wape is not None else None}


def forecast_monthly(points: list[dict], horizon: int) -> dict:
    values = [float(p["total"]) for p in points]
    months = [int(p["month"]) for p in points]
    n = len(values)
    contiguous = _consecutive(points)
    # Require two complete annual cycles for seasonality. An incomplete
    # monthly sequence cannot safely establish repeated calendar effects.
    seasonal_eligible = n >= 24 and contiguous
    validation_size = min(12, max(3, n // 4)) if n >= 9 else 0
    if n - validation_size < 6:
        validation_size = 0
    actual, predicted_by_model = [], {"linear_regression": [], "seasonal_trend": []}
    if validation_size:
        for i in range(n - validation_size, n):
            actual.append(values[i])
            for model_name in predicted_by_model:
                if model_name == "seasonal_trend" and (not seasonal_eligible or i < 24):
                    continue
                predictor, _ = _fit(values[:i], months[:i], model_name == "seasonal_trend")
                predicted_by_model[model_name].append(predictor(i, months[i]))

    linear_scores = _metrics(actual, predicted_by_model["linear_regression"]) if actual else None
    seasonal_scores = (_metrics(actual, predicted_by_model["seasonal_trend"])
                       if seasonal_eligible and len(predicted_by_model["seasonal_trend"]) == len(actual) and actual else None)
    selected = ("seasonal_trend" if seasonal_scores and linear_scores and
                seasonal_scores["mae"] < linear_scores["mae"] * 0.97
                else "linear_regression")
    predictor, effects = _fit(values, months, selected == "seasonal_trend")
    selected_scores = seasonal_scores if selected == "seasonal_trend" else linear_scores

    last_year, last_month = int(points[-1]["year"]), int(points[-1]["month"])
    result = []
    for step in range(1, horizon + 1):
        absolute = last_year * 12 + last_month - 1 + step
        year, month = absolute // 12, absolute % 12 + 1
        prediction = predictor(n + step - 1, month)
        # Empirical backtest MAE is a descriptive uncertainty band, not a
        # statistically calibrated 95% confidence interval.
        uncertainty = (selected_scores or {}).get("mae")
        result.append({"year": year, "month": month,
                       "predicted_total": round(prediction, 2),
                       "lower_estimate": round(max(0.0, prediction - uncertainty), 2) if uncertainty is not None else None,
                       "upper_estimate": round(prediction + uncertainty, 2) if uncertainty is not None else None})

    # Report recurring patterns only if they have at least two observations,
    # and the monthly effect is material relative to the series mean.
    monthly_patterns = []
    if selected == "seasonal_trend":
        threshold = max(mean(values) * 0.05, 0.01)
        for month in range(1, 13):
            observations = sum(m == month for m in months)
            effect = effects[month]
            if observations >= 2 and abs(effect) >= threshold:
                monthly_patterns.append({
                    "month": month, "direction": "increase" if effect > 0 else "decrease",
                    "estimated_effect": round(effect, 2),
                    "observations": observations,
                })
        monthly_patterns.sort(key=lambda p: p["month"])

    warning = (
        "Modelo estacional seleccionado por menor error en validación temporal. "
        "Los patrones reflejan los datos históricos, no causas externas demostradas."
        if selected == "seasonal_trend" else
        "No se verificó una mejora estacional suficiente; se utiliza tendencia lineal. "
        "Se requieren al menos 24 meses consecutivos para evaluar estacionalidad."
    )
    return {"model": selected, "forecast": result, "validation": {
        "method": "expanding_window", "months": len(actual),
        "selected": selected_scores, "linear": linear_scores,
        "seasonal": seasonal_scores,
    }, "r2_score": selected_scores["r2"] if selected_scores else None,
        "seasonal_patterns": monthly_patterns,
        "seasonality_evaluated": seasonal_eligible,
        "warning": warning + " Los intervalos mostrados son bandas orientativas de ±MAE, no intervalos de confianza."}

"""Monthly forecasts: comparable rolling-origin backtests and seasonal patterns.

All predictions in validation are fitted using observations strictly before
their origin. Annual effects require at least two full cycles and continuity.
The uncertainty envelope is empirical error, NOT a confidence interval.
"""
from __future__ import annotations

from math import isfinite, sqrt
from statistics import mean, median
from sklearn.linear_model import LinearRegression


def _ordinal(point: dict) -> int:
    year, month = int(point["year"]), int(point["month"])
    if not 1 <= month <= 12:
        raise ValueError("La serie contiene un mes fuera del rango 1-12.")
    return year * 12 + month - 1


def _validated(points: list[dict]) -> tuple[list[float], list[int], list[int], list[int]]:
    if len(points) < 3:
        raise ValueError("Se requieren al menos 3 meses observados.")
    dates = [_ordinal(item) for item in points]
    if any(right <= left for left, right in zip(dates, dates[1:])):
        raise ValueError("Los períodos deben estar ordenados y no pueden repetirse.")
    values = [float(item["total"]) for item in points]
    if not all(isfinite(item) for item in values):
        raise ValueError("La serie contiene valores no finitos.")
    return values, dates, [int(item["month"]) for item in points], [
        right - left - 1 for left, right in zip(dates, dates[1:])
    ]


def _consecutive(points: list[dict]) -> bool:
    dates = [_ordinal(item) for item in points]
    return all(b - a == 1 for a, b in zip(dates, dates[1:]))


def _metrics(actual: list[float], predicted: list[float]) -> dict:
    if not actual or len(actual) != len(predicted):
        raise ValueError("No hay pares de validación comparables.")
    errors = [abs(a - p) for a, p in zip(actual, predicted)]
    mae = mean(errors)
    rmse = sqrt(mean([(a - p) ** 2 for a, p in zip(actual, predicted)]))
    average = mean(actual)
    denominator = sum((a - average) ** 2 for a in actual)
    r2 = 1 - sum((a - p) ** 2 for a, p in zip(actual, predicted)) / denominator if denominator > 0 else None
    total_actual = sum(abs(a) for a in actual)
    wape = 100 * sum(errors) / total_actual if total_actual > 0 else None
    return {"mae": round(mae, 2), "rmse": round(rmse, 2),
            "r2": round(r2, 4) if r2 is not None else None,
            "wape": round(wape, 2) if wape is not None else None,
            "samples": len(actual)}


def _fit(values: list[float], dates: list[int], seasonal: bool):
    """Fit a calendar-aware trend and shrunk month-specific residual effects."""
    origin = dates[0]
    x = [[date - origin] for date in dates]
    trend = LinearRegression().fit(x, values)
    effects = {month: 0.0 for month in range(1, 13)}
    if seasonal:
        residuals = [value - float(trend.predict([[date - origin]])[0])
                     for value, date in zip(values, dates)]
        for month in range(1, 13):
            matching = [residual for residual, date in zip(residuals, dates)
                        if date % 12 + 1 == month]
            if len(matching) >= 2:
                effects[month] = median(matching) * len(matching) / (len(matching) + 0.75)
        center = mean(effects.values())
        effects = {month: effect - center for month, effect in effects.items()}

    def predict(date: int) -> float:
        return max(0.0, float(trend.predict([[date - origin]])[0]) + effects[date % 12 + 1])

    return predict, effects


def _predictor(model: str, values: list[float], dates: list[int]):
    if model == "naive_last":
        last = values[-1]
        return lambda date: max(0.0, last), {}
    if model == "seasonal_naive":
        # Use the corresponding month from the most recent available year.
        lookup = {date: value for date, value in zip(dates, values)}
        def predict(date: int) -> float:
            reference = date - 12
            while reference > dates[-1]:
                reference -= 12
            return max(0.0, lookup[reference])
        return predict, {}
    return _fit(values, dates, model == "seasonal_trend")


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    left = int(position)
    right = min(left + 1, len(ordered) - 1)
    return ordered[left] + (ordered[right] - ordered[left]) * (position - left)


def forecast_monthly(points: list[dict], horizon: int) -> dict:
    if not 1 <= horizon <= 12:
        raise ValueError("El horizonte debe estar entre 1 y 12 meses.")
    values, dates, months, gaps = _validated(points)
    n = len(values)
    contiguous = all(gap == 0 for gap in gaps)
    seasonal_eligible = contiguous and n >= 26  # 24 train + >=2 evaluation origins
    eligible = ["naive_last", "linear_regression"]
    if seasonal_eligible:
        eligible += ["seasonal_naive", "seasonal_trend"]

    # Same calendar targets and forecast leads across all candidate models.
    # When seasonal models participate, all origins have 24+ months of training.
    start = max(24 if seasonal_eligible else 6, n - 12)
    origins = list(range(start, n))
    actual = []
    candidates = {name: [] for name in eligible}
    residuals = {name: [] for name in eligible}
    if origins:
        for origin in origins:
            future = range(origin, min(n, origin + horizon))
            real = [values[index] for index in future]
            actual.extend(real)
            for name in eligible:
                predict, _ = _predictor(name, values[:origin], dates[:origin])
                estimated = [predict(dates[index]) for index in future]
                candidates[name].extend(estimated)
                residuals[name].extend([abs(a - b) for a, b in zip(real, estimated)])

    scores = {name: _metrics(actual, predictions) for name, predictions in candidates.items()
              if actual}
    if scores:
        best = min(scores, key=lambda name: (scores[name]["mae"], scores[name]["rmse"]))
        # Do not select a complex seasonal model for a negligible advantage.
        simple_best = min((name for name in scores if name in ("naive_last", "linear_regression")),
                          key=lambda name: scores[name]["mae"])
        if best in ("seasonal_trend", "seasonal_naive") and (
            scores[best]["mae"] >= scores[simple_best]["mae"] * 0.97
        ):
            best = simple_best
    else:
        best = "naive_last"
    predictor, effects = _predictor(best, values, dates)
    selected_scores = scores.get(best)
    # Descriptive absolute-error band, derived solely from historical backtests.
    error_band = _percentile(residuals.get(best, []), 0.8) if len(actual) >= 6 else None
    last = dates[-1]
    forecast = []
    for step in range(1, horizon + 1):
        target = last + step
        value = predictor(target)
        forecast.append({
            "year": target // 12, "month": target % 12 + 1,
            "predicted_total": round(value, 2),
            "lower_estimate": round(max(0.0, value - error_band), 2) if error_band is not None else None,
            "upper_estimate": round(value + error_band, 2) if error_band is not None else None,
        })

    monthly_patterns = []
    if best in ("seasonal_trend", "seasonal_naive") and contiguous:
        _, effects = _fit(values, dates, True)
        threshold = max(mean(abs(v) for v in values) * 0.05, 0.01)
        for month in range(1, 13):
            observation_count = months.count(month)
            if observation_count < 2 or abs(effects[month]) < threshold:
                continue
            monthly_patterns.append({
                "month": month,
                "direction": "increase" if effects[month] > 0 else "decrease",
                "estimated_effect": round(effects[month], 2),
                "observations": observation_count,
            })

    baseline = scores.get("naive_last")
    skill = (round(100 * (1 - selected_scores["mae"] / baseline["mae"]), 2)
             if selected_scores and baseline and baseline["mae"] > 0 else None)
    warnings = []
    if gaps and any(gaps):
        warnings.append(f"Hay {sum(gaps)} mes(es) sin registros entre observaciones; "
                        "no se asumieron ceros ni se evaluó estacionalidad.")
    if n < 24:
        warnings.append("Menos de 24 meses: los ciclos anuales no pueden verificarse.")
    elif not seasonal_eligible:
        warnings.append("La serie necesita al menos 26 meses consecutivos para validar modelos anuales.")
    if not actual:
        warnings.append("Historial insuficiente para backtesting fuera del entrenamiento.")
    elif len(actual) < 12:
        warnings.append("Evaluación limitada: menos de 12 pares históricos.")
    if selected_scores and skill is not None and skill <= 0:
        warnings.append("El modelo no mejora el pronóstico ingenuo de repetir el último mes.")
    warnings.append("Las bandas son errores absolutos históricos aproximados (percentil 80), "
                    "no intervalos de confianza ni garantías.")
    confidence = ("insufficient" if len(actual) < 6 else
                  "limited" if not seasonal_eligible or len(origins) < 6 or skill is None else
                  "moderate" if skill > 10 else "limited")
    return {
        "model": best, "forecast": forecast,
        "validation": {
            "method": "rolling_origin_multi_horizon", "months": len(origins),
            "samples": len(actual), "horizon": horizon,
            "selected": selected_scores, "linear": scores.get("linear_regression"),
            "seasonal": scores.get("seasonal_trend"),
            "baseline": baseline, "candidates": scores,
            "skill_vs_naive_pct": skill,
            "band": {"kind": "empirical_absolute_error_p80", "value": round(error_band, 2)
                     if error_band is not None else None},
        },
        "r2_score": selected_scores["r2"] if selected_scores else None,
        "seasonal_patterns": monthly_patterns,
        "seasonality_evaluated": seasonal_eligible,
        "data_quality": {"observed_months": n, "missing_months": sum(gaps),
                         "continuous": contiguous},
        "confidence": confidence, "warnings": warnings, "warning": " ".join(warnings),
    }

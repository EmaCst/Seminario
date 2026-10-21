"""Monthly forecasts: comparable rolling-origin backtests and seasonal patterns.

All predictions in validation are fitted using observations strictly before
their origin. Annual effects require at least two full cycles and continuity.
The uncertainty envelope is empirical error, NOT a confidence interval.
"""
from __future__ import annotations

from datetime import date
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


def _fit(values: list[float], dates: list[int], seasonal: bool, nonnegative: bool = True):
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
        value = float(trend.predict([[date - origin]])[0]) + effects[date % 12 + 1]
        return max(0.0, value) if nonnegative else value

    return predict, effects


def _predictor(model: str, values: list[float], dates: list[int], nonnegative: bool = True):
    if model == "naive_last":
        last = values[-1]
        return lambda date: max(0.0, last) if nonnegative else last, {}
    if model == "seasonal_naive":
        # Benchmark ONLY. This repeats last year's observed month verbatim.
        lookup = {date: value for date, value in zip(dates, values)}
        def predict(date: int) -> float:
            reference = date - 12
            while reference > dates[-1]:
                reference -= 12
            value = lookup[reference]
            return max(0.0, value) if nonnegative else value
        return predict, {}
    if model == "seasonal_drift":
        # Forecast each future calendar month using multiple previous years,
        # corrected with the robust typical year-over-year *level change*.
        # Unlike seasonal_naive this estimates evolution and is resistant to
        # one unusually high/low observation in the preceding year.
        lookup = dict(zip(dates, values))
        changes = [value - lookup[day - 12] for day, value in zip(dates, values)
                   if day - 12 in lookup]
        if len(changes) < 12:
            raise ValueError("El modelo estacional ajustado requiere 12 comparaciones interanuales.")
        annual_drift = median(changes[-24:])
        def predict(date: int) -> float:
            historical = [
                value + annual_drift * ((date - day) / 12.0)
                for day, value in zip(dates, values)
                if day % 12 == date % 12 and day < date
            ]
            if len(historical) < 2:
                raise ValueError("Sin observaciones históricas para el mes proyectado.")
            value = median(historical)
            return max(0.0, value) if nonnegative else value
        return predict, {"annual_drift": annual_drift}
    return _fit(values, dates, model == "seasonal_trend", nonnegative=nonnegative)


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    left = int(position)
    right = min(left + 1, len(ordered) - 1)
    return ordered[left] + (ordered[right] - ordered[left]) * (position - left)


def forecast_monthly(points: list[dict], horizon: int, *, nonnegative: bool = True) -> dict:
    if not 1 <= horizon <= 12:
        raise ValueError("El horizonte debe estar entre 1 y 12 meses.")
    values, dates, months, gaps = _validated(points)
    n = len(values)
    contiguous = all(gap == 0 for gap in gaps)
    seasonal_eligible = contiguous and n >= 26  # 24 train + >=2 evaluation origins
    eligible = ["naive_last", "linear_regression"]
    if seasonal_eligible:
        # seasonal_naive is scored to keep the honest benchmark, but it is
        # never eligible for selection as a newly calculated forecast.
        eligible += ["seasonal_naive", "seasonal_trend", "seasonal_drift"]

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
                predict, _ = _predictor(name, values[:origin], dates[:origin], nonnegative)
                estimated = [predict(dates[index]) for index in future]
                candidates[name].extend(estimated)
                residuals[name].extend([abs(a - b) for a, b in zip(real, estimated)])

    scores = {name: _metrics(actual, predictions) for name, predictions in candidates.items()
              if actual}
    if scores:
        selectable = [name for name in scores if name != "seasonal_naive"]
        best = min(selectable, key=lambda name: (scores[name]["mae"], scores[name]["rmse"]))
        # Do not select a complex seasonal model for a negligible advantage.
        simple_best = min((name for name in selectable if name in ("naive_last", "linear_regression")),
                          key=lambda name: scores[name]["mae"])
        if best in ("seasonal_trend", "seasonal_drift") and (
            scores[best]["mae"] >= scores[simple_best]["mae"] * 0.97
        ):
            best = simple_best
    else:
        best = "naive_last"
    predictor, effects = _predictor(best, values, dates, nonnegative)
    selected_scores = scores.get(best)
    # Descriptive absolute-error band, derived solely from historical backtests.
    error_band = _percentile(residuals.get(best, []), 0.8) if len(actual) >= 6 else None
    last = dates[-1]
    observed_by_date = dict(zip(dates, values))
    today = date.today()
    current_period = today.year * 12 + today.month - 1
    forecast = []
    for step in range(1, horizon + 1):
        target = last + step
        value = predictor(target)
        prior_year_value = observed_by_date.get(target - 12)
        if target < current_period:
            period_status = "historical_gap"
        elif target == current_period:
            period_status = "current_month"
        else:
            period_status = "future"
        forecast.append({
            "year": target // 12, "month": target % 12 + 1,
            "predicted_total": round(value, 2),
            "prior_year_total": round(prior_year_value, 2) if prior_year_value is not None else None,
            "change_vs_prior_year": round(value - prior_year_value, 2) if prior_year_value is not None else None,
            "value_kind": "model_estimate" if best not in ("naive_last", "seasonal_naive") else "baseline_estimate",
            "period_status": period_status,
            "lower_estimate": round(max(0.0, value - error_band) if nonnegative else value - error_band, 2) if error_band is not None else None,
            "upper_estimate": round(value + error_band, 2) if error_band is not None else None,
        })

    monthly_patterns = []
    if best in ("seasonal_trend", "seasonal_drift") and contiguous:
        _, effects = _fit(values, dates, True, nonnegative=nonnegative)
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
    annual_baseline = scores.get("seasonal_naive")
    skill = (round(100 * (1 - selected_scores["mae"] / baseline["mae"]), 2)
             if selected_scores and baseline and baseline["mae"] > 0 else None)
    warnings = []
    if any(item["period_status"] == "historical_gap" for item in forecast):
        warnings.append(
            "ATENCIÓN: el historial termina antes de los períodos proyectados y "
            "parte de estos períodos ya transcurrió. Son estimaciones posteriores "
            "al último registro, NO pronósticos del futuro desde hoy."
        )
    if any(item["period_status"] == "current_month" for item in forecast):
        warnings.append(
            "La proyección incluye el mes calendario actual, no necesariamente "
            "un mes futuro completo."
        )
    if last == current_period:
        warnings.append(
            "El último mes registrado coincide con el mes actual: podría incluir "
            "únicamente datos parciales y distorsionar tendencias o patrones estacionales."
        )
    if last > current_period:
        warnings.append(
            "El último registro tiene una fecha posterior al mes actual; "
            "revisa el origen temporal de los datos."
        )
    if best == "naive_last":
        warnings.append(
            "Se utiliza una referencia sencilla: repetir el último valor registrado. "
            "No es evidencia de que una tendencia o ciclo predictivo haya mejorado esa referencia."
        )
    if annual_baseline and selected_scores and (
        selected_scores["mae"] > annual_baseline["mae"] * 1.03
    ):
        warnings.append(
            "La proyección calculada NO supera en validación histórica la referencia "
            "de repetir el mismo mes del año anterior; interpreta el resultado con cautela."
        )
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
                  "limited" if not seasonal_eligible or len(origins) < 6 or skill is None
                  or best == "naive_last"
                  or (annual_baseline and selected_scores and
                      selected_scores["mae"] > annual_baseline["mae"] * 1.03)
                  else "moderate" if skill > 10 else "limited")
    return {
        "model": best, "forecast": forecast,
        "validation": {
            "method": "rolling_origin_multi_horizon", "months": len(origins),
            "samples": len(actual), "horizon": horizon,
            "selected": selected_scores, "linear": scores.get("linear_regression"),
            "seasonal": scores.get("seasonal_trend"),
            "baseline": baseline, "seasonal_baseline": annual_baseline,
            "candidates": scores,
            "skill_vs_naive_pct": skill,
            "band": {"kind": "empirical_absolute_error_p80", "value": round(error_band, 2)
                     if error_band is not None else None},
        },
        "r2_score": selected_scores["r2"] if selected_scores else None,
        "seasonal_patterns": monthly_patterns,
        "seasonality_evaluated": seasonal_eligible,
        "forecast_basis": {
            "last_observed": {"year": last // 12, "month": last % 12 + 1},
            "first_projected": {"year": forecast[0]["year"], "month": forecast[0]["month"]},
            "last_projected": {"year": forecast[-1]["year"], "month": forecast[-1]["month"]},
            "as_of": today.isoformat(),
            "source": "last_observed_month",
            "all_periods_future": all(item["period_status"] == "future" for item in forecast),
            "model_origin": "fitted_to_history" if best not in ("naive_last", "seasonal_naive")
                            else "baseline_reference",
        },
        "data_quality": {"observed_months": n, "missing_months": sum(gaps),
                         "continuous": contiguous},
        "confidence": confidence, "warnings": warnings, "warning": " ".join(warnings),
    }

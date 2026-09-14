from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, pstdev

from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression

from app.analysis.adaptive_dashboard_service import _monthly_count
from app.analysis.semantic_mapper_v2 import inspect_semantic_model


@dataclass
class TimeSeriesCandidate:
    role: str
    table: str
    date_column: str
    data: list[dict]


def _find_best_time_series() -> TimeSeriesCandidate:
    analysis = inspect_semantic_model()
    semantic = analysis.get("semantic_model") or {}
    entities = semantic.get("entities") or {}

    candidates: list[TimeSeriesCandidate] = []

    for role, entity in entities.items():
        table = entity.get("table")
        date_column = (entity.get("columns") or {}).get("date")
        if not table or not date_column:
            continue

        try:
            data = _monthly_count(table, date_column)
        except Exception:
            continue

        if data:
            candidates.append(
                TimeSeriesCandidate(
                    role=role,
                    table=table,
                    date_column=date_column,
                    data=data,
                )
            )

    if not candidates:
        raise ValueError(
            "No se encontró ninguna entidad con columna de fecha y datos suficientes para análisis temporal."
        )

    candidates.sort(key=lambda item: len(item.data), reverse=True)
    return candidates[0]


def _next_year_month(year: int, month: int, offset: int) -> tuple[int, int]:
    absolute = year * 12 + (month - 1) + offset
    return absolute // 12, (absolute % 12) + 1


def _percentage_change(value: float, baseline: float | None) -> float | None:
    if baseline is None or baseline == 0:
        return None
    return round(((value - baseline) / baseline) * 100.0, 2)


def _severity_from_context(z_score: float | None, pct_vs_average: float | None) -> str:
    abs_z = abs(z_score or 0.0)
    abs_pct = abs(pct_vs_average or 0.0)

    if abs_z >= 2.0 or abs_pct >= 60:
        return "alta"
    if abs_z >= 1.25 or abs_pct >= 35:
        return "media"
    return "baja"


def _build_anomaly_explanation(
    value: float,
    average: float,
    pct_vs_average: float | None,
    previous_value: float | None,
    pct_vs_previous: float | None,
    neighbor_average: float | None,
    pct_vs_neighbors: float | None,
) -> str:
    direction = "por encima" if value >= average else "por debajo"
    parts = []

    if pct_vs_average is not None:
        parts.append(
            f"el valor {value:g} quedó {abs(pct_vs_average):.1f}% {direction} "
            f"del promedio mensual ({average:.2f})"
        )

    if previous_value is not None and pct_vs_previous is not None:
        prev_direction = "aumentó" if pct_vs_previous >= 0 else "disminuyó"
        parts.append(
            f"{prev_direction} {abs(pct_vs_previous):.1f}% frente al mes anterior ({previous_value:g})"
        )

    if neighbor_average is not None and pct_vs_neighbors is not None:
        neighbor_direction = "por encima" if pct_vs_neighbors >= 0 else "por debajo"
        parts.append(
            f"quedó {abs(pct_vs_neighbors):.1f}% {neighbor_direction} del promedio de los meses vecinos "
            f"({neighbor_average:.2f})"
        )

    if not parts:
        return "El modelo Isolation Forest identificó este punto como diferente al patrón mensual habitual."

    return "Se considera atípico porque " + "; además, ".join(parts) + "."


def forecast_next_months(horizon: int = 3) -> dict:
    if horizon < 1 or horizon > 12:
        raise ValueError("El horizonte debe estar entre 1 y 12 meses.")

    series = _find_best_time_series()
    points = series.data

    if len(points) < 3:
        raise ValueError(
            f"La serie temporal más completa ({series.role}) solo tiene {len(points)} mes(es). "
            "Se requieren al menos 3 meses para generar una predicción básica."
        )

    x = [[index] for index in range(len(points))]
    y = [float(item["total"]) for item in points]

    model = LinearRegression()
    model.fit(x, y)

    future_x = [[len(points) + step] for step in range(horizon)]
    future_values = model.predict(future_x)

    last = points[-1]
    forecast = []
    for step, value in enumerate(future_values, start=1):
        year, month = _next_year_month(int(last["year"]), int(last["month"]), step)
        forecast.append(
            {
                "year": year,
                "month": month,
                "predicted_total": round(max(0.0, float(value)), 2),
            }
        )

    return {
        "model": "linear_regression",
        "role": series.role,
        "table": series.table,
        "date_column": series.date_column,
        "training_points": points,
        "training_months": len(points),
        "r2_score": round(float(model.score(x, y)), 4) if len(points) > 1 else None,
        "forecast": forecast,
        "warning": (
            "Predicción exploratoria basada únicamente en la tendencia histórica mensual. "
            "No debe interpretarse como una garantía de resultados futuros."
        ),
    }


def detect_monthly_anomalies() -> dict:
    series = _find_best_time_series()
    points = series.data

    if len(points) < 4:
        raise ValueError(
            f"La serie temporal más completa ({series.role}) solo tiene {len(points)} mes(es). "
            "Se requieren al menos 4 meses para detectar anomalías."
        )

    raw_values = [float(item["total"]) for item in points]
    values = [[value] for value in raw_values]
    contamination = min(0.25, max(1.0 / len(values), 0.05))

    model = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
    )
    labels = model.fit_predict(values)
    scores = model.decision_function(values)

    average = mean(raw_values)
    med = median(raw_values)
    std_dev = pstdev(raw_values) if len(raw_values) > 1 else 0.0

    anomalies = []
    evaluated = []

    for index, (point, label, score) in enumerate(zip(points, labels, scores)):
        value = float(point["total"])
        previous_value = raw_values[index - 1] if index > 0 else None
        next_value = raw_values[index + 1] if index < len(raw_values) - 1 else None

        neighbors = [item for item in (previous_value, next_value) if item is not None]
        neighbor_average = mean(neighbors) if neighbors else None

        pct_vs_average = _percentage_change(value, average)
        pct_vs_previous = _percentage_change(value, previous_value)
        pct_vs_neighbors = _percentage_change(value, neighbor_average)
        z_score = round((value - average) / std_dev, 3) if std_dev > 0 else None
        severity = _severity_from_context(z_score, pct_vs_average)

        reason = _build_anomaly_explanation(
            value=value,
            average=average,
            pct_vs_average=pct_vs_average,
            previous_value=previous_value,
            pct_vs_previous=pct_vs_previous,
            neighbor_average=neighbor_average,
            pct_vs_neighbors=pct_vs_neighbors,
        )

        item = {
            **point,
            "anomaly": bool(label == -1),
            "anomaly_score": round(float(score), 4),
            "severity": severity if label == -1 else None,
            "direction": "spike" if value >= average else "drop",
            "series_average": round(average, 2),
            "series_median": round(med, 2),
            "series_std_dev": round(std_dev, 2),
            "z_score": z_score,
            "previous_total": previous_value,
            "next_total": next_value,
            "neighbor_average": round(neighbor_average, 2) if neighbor_average is not None else None,
            "pct_vs_average": pct_vs_average,
            "pct_vs_previous": pct_vs_previous,
            "pct_vs_neighbors": pct_vs_neighbors,
            "reason": reason if label == -1 else None,
        }
        evaluated.append(item)
        if label == -1:
            anomalies.append(item)

    return {
        "model": "isolation_forest",
        "role": series.role,
        "table": series.table,
        "date_column": series.date_column,
        "months_evaluated": len(points),
        "baseline": {
            "average": round(average, 2),
            "median": round(med, 2),
            "std_dev": round(std_dev, 2),
        },
        "anomalies": anomalies,
        "series": evaluated,
    }

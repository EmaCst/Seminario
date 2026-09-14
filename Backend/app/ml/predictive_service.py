from __future__ import annotations

from dataclasses import dataclass

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

    # Preferimos la serie con más meses distintos para no sesgar el modelo a una
    # entidad con un único periodo (por ejemplo, inscripciones de enero).
    candidates.sort(key=lambda item: len(item.data), reverse=True)
    return candidates[0]


def _next_year_month(year: int, month: int, offset: int) -> tuple[int, int]:
    absolute = year * 12 + (month - 1) + offset
    return absolute // 12, (absolute % 12) + 1


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

    values = [[float(item["total"])] for item in points]
    contamination = min(0.25, max(1.0 / len(values), 0.05))

    model = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
    )
    labels = model.fit_predict(values)
    scores = model.decision_function(values)

    anomalies = []
    evaluated = []

    for point, label, score in zip(points, labels, scores):
        item = {
            **point,
            "anomaly": bool(label == -1),
            "anomaly_score": round(float(score), 4),
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
        "anomalies": anomalies,
        "series": evaluated,
    }

import re
from time import perf_counter

from app.ai.gemma import explain_results, generate_sql
from app.database.query_executor import execute_query
from app.ml.predictive_service import detect_monthly_anomalies, forecast_next_months


PREDICTION_TERMS = (
    "predice", "predecir", "predicción", "prediccion", "pronostica", "pronosticar",
    "pronóstico", "pronostico", "proyección", "proyeccion", "forecast", "predict",
    "prediction", "next month", "next months", "próximo mes", "proximo mes",
    "próximos meses", "proximos meses",
)

ANOMALY_TERMS = (
    "anomal", "atíp", "atip", "extraño", "extrano", "inusual", "fuera de lo normal",
    "comportamiento raro", "outlier", "unusual", "abnormal",
)


def _extract_horizon(question: str, default: int = 3) -> int:
    text = question.lower()
    patterns = (
        r"(?:pr[oó]xim(?:os|as)?|siguientes?)\s+(\d{1,2})\s+mes",
        r"next\s+(\d{1,2})\s+month",
        r"(?:a|para)\s+(\d{1,2})\s+mes",
        r"(\d{1,2})\s+mes(?:es)?",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return max(1, min(12, int(match.group(1))))
    return default


def _is_prediction_request(question: str) -> bool:
    text = question.lower()
    return any(term in text for term in PREDICTION_TERMS)


def _is_anomaly_request(question: str) -> bool:
    text = question.lower()
    return any(term in text for term in ANOMALY_TERMS)


def _quality_from_r2(r2: float | None) -> str:
    if r2 is None:
        return "desconocida"
    if r2 >= 0.75:
        return "alta"
    if r2 >= 0.50:
        return "media"
    if r2 >= 0.25:
        return "baja"
    return "muy baja"


def _format_forecast_answer(result: dict) -> str:
    role = result.get("role", "serie")
    forecast = result.get("forecast") or []
    r2 = result.get("r2_score")
    quality = _quality_from_r2(r2)

    if not forecast:
        return "No pude generar una predicción con los datos disponibles."

    values = ", ".join(
        f"{item['month']:02d}/{item['year']}: {item['predicted_total']}"
        for item in forecast
    )

    if isinstance(r2, (int, float)):
        explanation = (
            f"La calidad de ajuste del modelo es {quality} (R²={r2:.4f}), "
            "así que conviene interpretar estos valores como una tendencia estimada y no como una certeza."
        )
    else:
        explanation = "Tómalo como una estimación orientativa basada en el comportamiento histórico disponible."

    return (
        f"La proyección para {role} es: {values}. "
        f"{explanation}"
    )


def _format_anomaly_answer(result: dict) -> str:
    role = result.get("role", "serie")
    anomalies = result.get("anomalies") or []

    if not anomalies:
        return f"No encontré meses que se alejen de forma relevante del comportamiento habitual de {role}."

    descriptions = []
    for item in anomalies:
        month = f"{item['month']:02d}/{item['year']}"
        total = item.get("total")
        severity = item.get("severity") or "no determinada"
        pct_average = item.get("pct_vs_average")
        pct_previous = item.get("pct_vs_previous")
        pct_neighbors = item.get("pct_vs_neighbors")

        reasons = []
        if isinstance(pct_average, (int, float)):
            direction = "por encima" if pct_average >= 0 else "por debajo"
            reasons.append(f"estuvo {abs(pct_average):.1f}% {direction} del promedio mensual")
        if isinstance(pct_previous, (int, float)):
            direction = "subió" if pct_previous >= 0 else "bajó"
            reasons.append(f"{direction} {abs(pct_previous):.1f}% frente al mes anterior")
        if isinstance(pct_neighbors, (int, float)):
            direction = "por encima" if pct_neighbors >= 0 else "por debajo"
            reasons.append(f"quedó {abs(pct_neighbors):.1f}% {direction} de sus meses vecinos")

        if reasons:
            reason_text = "; además, ".join(reasons)
        else:
            reason_text = item.get("reason") or "se alejó del patrón mensual habitual"

        descriptions.append(
            f"{month} registró {total} y fue clasificado con severidad {severity}: {reason_text}."
        )

    interpretation = (
        "Vale la pena revisar qué ocurrió en esos periodos para identificar posibles factores del negocio que expliquen el cambio."
    )

    return (
        f"Detecté {len(anomalies)} comportamiento(s) atípico(s) en {role}. "
        + " ".join(descriptions)
        + " "
        + interpretation
    )


def ask_database(question: str) -> dict:
    """Orquesta SQL, predicciones y anomalías según la intención de la pregunta."""
    started = perf_counter()

    if _is_prediction_request(question):
        ml_started = perf_counter()
        horizon = _extract_horizon(question)
        result = forecast_next_months(horizon=horizon)
        return {
            "question": question,
            "mode": "forecast",
            "sql": None,
            "data": result,
            "answer": _format_forecast_answer(result),
            "performance": {
                "ml_ms": round((perf_counter() - ml_started) * 1000, 1),
                "total_ms": round((perf_counter() - started) * 1000, 1),
            },
        }

    if _is_anomaly_request(question):
        ml_started = perf_counter()
        result = detect_monthly_anomalies()
        return {
            "question": question,
            "mode": "anomalies",
            "sql": None,
            "data": result,
            "answer": _format_anomaly_answer(result),
            "performance": {
                "ml_ms": round((perf_counter() - ml_started) * 1000, 1),
                "total_ms": round((perf_counter() - started) * 1000, 1),
            },
        }

    sql_started = perf_counter()
    sql = generate_sql(question)
    sql_seconds = perf_counter() - sql_started

    query_started = perf_counter()
    results = execute_query(sql)
    query_seconds = perf_counter() - query_started

    explanation_started = perf_counter()
    answer = explain_results(question=question, sql=sql, results=results)
    explanation_seconds = perf_counter() - explanation_started

    return {
        "question": question,
        "mode": "sql",
        "sql": sql,
        "data": results,
        "answer": answer,
        "performance": {
            "sql_generation_ms": round(sql_seconds * 1000, 1),
            "database_query_ms": round(query_seconds * 1000, 1),
            "explanation_ms": round(explanation_seconds * 1000, 1),
            "total_ms": round((perf_counter() - started) * 1000, 1),
        },
    }

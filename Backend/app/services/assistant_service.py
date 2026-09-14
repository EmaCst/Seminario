import re
from time import perf_counter

from app.ai.gemma import explain_results, generate_sql, repair_sql
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


def _intent_text(question: str, history: list[dict] | None) -> str:
    """Permite entender follow-ups cortos como '¿y para 6 meses?'."""
    recent_user = []
    for item in (history or [])[-6:]:
        role = item.get("role") or item.get("from")
        if role not in {"user", "usuario"}:
            continue
        content = str(item.get("content") or item.get("text") or "").strip()
        if content:
            recent_user.append(content)
    return " ".join(recent_user[-2:] + [question]).lower()


def _is_prediction_request(text: str) -> bool:
    return any(term in text for term in PREDICTION_TERMS)


def _is_anomaly_request(text: str) -> bool:
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
            f"La calidad de ajuste es {quality} (R²={r2:.4f}), "
            "así que conviene tomarlo como una tendencia estimada, no como una certeza."
        )
    else:
        explanation = "Tómalo como una estimación orientativa basada en el historial disponible."

    return f"La proyección para {role} es: {values}. {explanation}"


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

        reason_text = "; además, ".join(reasons) if reasons else "se alejó del patrón mensual habitual"
        descriptions.append(
            f"{month} registró {total} y tuvo severidad {severity}: {reason_text}."
        )

    return (
        f"Detecté {len(anomalies)} comportamiento(s) atípico(s) en {role}. "
        + " ".join(descriptions)
        + " Vale la pena revisar qué ocurrió en esos periodos para entender el cambio."
    )


def _format_value(value) -> str:
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:,.2f}"
    return str(value)


def _fast_answer(question: str, results: list[dict]) -> str | None:
    """Evita una segunda llamada al LLM para respuestas escalares muy simples."""
    if not results:
        return "No encontré resultados para esa consulta."

    if len(results) != 1:
        return None

    row = results[0]
    if not row or len(row) > 3:
        return None

    if len(row) == 1:
        key, value = next(iter(row.items()))
        raw_key = str(key or "").strip()
        key_text = raw_key.lower().replace("_", " ")
        q = question.lower()
        value_text = _format_value(value)

        if any(term in q for term in ("cuántas ventas", "cuantas ventas", "cantidad de ventas", "número de ventas", "numero de ventas")):
            return f"Hay {value_text} ventas en total."

        if any(term in q for term in ("cuánto dinero", "cuanto dinero", "monto", "importe", "facturación", "facturacion", "ingresos")):
            return f"El monto total es {value_text}."

        if raw_key:
            label = key_text.capitalize()
            return f"{label}: {value_text}."

        return f"El resultado es {value_text}."

    parts = []
    for key, value in row.items():
        raw_key = str(key or "").strip()
        label = raw_key.replace("_", " ").strip().capitalize() or "Resultado"
        parts.append(f"{label}: {_format_value(value)}")

    return ". ".join(parts) + "."


def ask_database(question: str, history: list[dict] | None = None) -> dict:
    """Orquesta SQL, ML, contexto conversacional y autocorrección."""
    started = perf_counter()
    history = history or []
    intent_text = _intent_text(question, history)

    if _is_prediction_request(intent_text):
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

    if _is_anomaly_request(intent_text):
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
    sql = generate_sql(question, history=history)
    sql_generation_seconds = perf_counter() - sql_started

    query_started = perf_counter()
    retried = False
    original_error = None
    retry_error = None

    try:
        results = execute_query(sql)
    except Exception as exc:
        retried = True
        original_error = str(exc)
        repair_started = perf_counter()
        try:
            sql = repair_sql(
                question=question,
                failed_sql=sql,
                error=original_error,
                history=history,
            )
            sql_generation_seconds += perf_counter() - repair_started
            results = execute_query(sql)
        except Exception as retry_exc:
            retry_error = str(retry_exc)
            return {
                "question": question,
                "mode": "error",
                "sql": None,
                "data": [],
                "answer": (
                    "No pude resolver esa consulta con suficiente seguridad. "
                    "Prueba reformulándola en una sola petición más concreta o vuelve a intentarlo."
                ),
                "recovery": {
                    "retried": True,
                    "initial_error": original_error,
                    "retry_error": retry_error,
                },
                "performance": {
                    "sql_generation_ms": round(sql_generation_seconds * 1000, 1),
                    "database_query_ms": round((perf_counter() - query_started) * 1000, 1),
                    "explanation_ms": 0.0,
                    "used_llm_explanation": False,
                    "total_ms": round((perf_counter() - started) * 1000, 1),
                },
            }

    query_seconds = perf_counter() - query_started

    explanation_started = perf_counter()
    answer = _fast_answer(question, results)
    used_llm_explanation = answer is None
    if answer is None:
        answer = explain_results(
            question=question,
            sql=sql,
            results=results,
            history=history,
        )
    explanation_seconds = perf_counter() - explanation_started

    return {
        "question": question,
        "mode": "sql",
        "sql": sql,
        "data": results,
        "answer": answer,
        "recovery": {
            "retried": retried,
            "initial_error": original_error if retried else None,
            "retry_error": retry_error,
        },
        "performance": {
            "sql_generation_ms": round(sql_generation_seconds * 1000, 1),
            "database_query_ms": round(query_seconds * 1000, 1),
            "explanation_ms": round(explanation_seconds * 1000, 1),
            "used_llm_explanation": used_llm_explanation,
            "total_ms": round((perf_counter() - started) * 1000, 1),
        },
    }

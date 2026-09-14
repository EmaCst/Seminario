from time import perf_counter

from app.ai.gemma import explain_results, generate_sql
from app.database.query_executor import execute_query


def ask_database(question: str) -> dict:
    """Ejecuta el pipeline de IA y expone tiempos por etapa para optimización."""

    started = perf_counter()

    sql_started = perf_counter()
    sql = generate_sql(question)
    sql_seconds = perf_counter() - sql_started

    query_started = perf_counter()
    results = execute_query(sql)
    query_seconds = perf_counter() - query_started

    explanation_started = perf_counter()
    answer = explain_results(
        question=question,
        sql=sql,
        results=results,
    )
    explanation_seconds = perf_counter() - explanation_started

    total_seconds = perf_counter() - started

    return {
        "question": question,
        "sql": sql,
        "data": results,
        "answer": answer,
        "performance": {
            "sql_generation_ms": round(sql_seconds * 1000, 1),
            "database_query_ms": round(query_seconds * 1000, 1),
            "explanation_ms": round(explanation_seconds * 1000, 1),
            "total_ms": round(total_seconds * 1000, 1),
        },
    }

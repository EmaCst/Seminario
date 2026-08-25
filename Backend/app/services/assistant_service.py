from app.ai.gemma import (
    explain_results,
    generate_sql,
)
from app.database.query_executor import execute_query


def ask_database(question: str) -> dict:

    # 1. Gemma genera SQL
    sql = generate_sql(question)

    # 2. El backend valida y ejecuta
    results = execute_query(sql)

    # 3. Gemma interpreta los resultados
    answer = explain_results(
        question=question,
        sql=sql,
        results=results
    )

    return {
        "question": question,
        "sql": sql,
        "data": results,
        "answer": answer
    }
from __future__ import annotations

from ollama import chat

from app.ai.database_context import get_compact_database_context
from app.ai.sql_normalizer import normalize_sql
from app.database.database_manager import database_manager


MODEL = "gemma3:4b"


def ask_gemma(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.1,
    num_predict: int = 220,
) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = chat(
        model=MODEL,
        messages=messages,
        keep_alive="30m",
        options={
            "temperature": temperature,
            "num_predict": num_predict,
        },
    )
    return response.message.content.strip()


def _active_dialect() -> str:
    return database_manager.status().get("provider") or "sqlserver"


def _dialect_label() -> str:
    return "PostgreSQL" if _active_dialect() == "postgresql" else "Microsoft SQL Server"


def _history_text(history: list[dict] | None, limit: int = 6) -> str:
    if not history:
        return ""

    normalized = []
    for item in history[-limit:]:
        role = item.get("role") or item.get("from") or "user"
        content = str(item.get("content") or item.get("text") or "").strip()
        if not content:
            continue
        label = "Usuario" if role in {"user", "usuario"} else "Kenneth"
        normalized.append(f"{label}: {content[:500]}")

    if not normalized:
        return ""
    return "\nCONTEXTO RECIENTE DE LA CONVERSACIÓN:\n" + "\n".join(normalized)


def analyze_database(question: str, history: list[dict] | None = None) -> str:
    database_context = get_compact_database_context()
    dialect_label = _dialect_label()

    prompt = f"""ESQUEMA REAL ({dialect_label}):
{database_context}
{_history_text(history)}

PREGUNTA ACTUAL:
{question}
"""

    return ask_gemma(
        prompt,
        system=(
            "Eres Kenneth, asistente empresarial especializado en bases de datos. "
            "Responde en español, usa solo información demostrable por el esquema, "
            "no inventes tablas, columnas ni relaciones y sé claro y breve."
        ),
        num_predict=220,
    )


def _dialect_rules() -> str:
    if _active_dialect() == "postgresql":
        return (
            "Motor PostgreSQL: usa LIMIT, nunca TOP; usa EXTRACT/DATE_TRUNC cuando corresponda. "
            "Puedes usar WITH, LAG, ROW_NUMBER, RANK y otras funciones de ventana nativas de PostgreSQL."
        )
    return (
        "Motor Microsoft SQL Server: usa TOP, nunca LIMIT; usa funciones de fecha compatibles con SQL Server. "
        "Puedes usar WITH, LAG, ROW_NUMBER, RANK y otras funciones de ventana compatibles con SQL Server."
    )


def _sql_system_prompt() -> str:
    return (
        "Eres un generador experto de SQL seguro. Devuelve únicamente UNA consulta de solo lectura en SQL plano, "
        "sin Markdown ni explicaciones. Puede comenzar con SELECT o con WITH si necesitas CTEs. "
        "Usa exclusivamente tablas, columnas y relaciones presentes en el esquema. No inventes nada. "
        "Respeta PK/FK y usa alias descriptivos para TODAS las métricas calculadas. "
        "La PREGUNTA ACTUAL tiene prioridad; el historial solo sirve para resolver referencias como 'y eso', "
        "'el anterior', 'ese cliente' o 'cuánto representan'. "
        "Interpreta 'cuántas ventas hay' como cantidad de transacciones/filas de ventas con COUNT, "
        "no como dinero. Interpreta 'cuánto dinero', 'monto', 'importe', 'ingresos' o 'facturación' como SUM "
        "de la columna monetaria real. Interpreta 'unidades vendidas' como SUM de una columna de cantidad. "
        "Para rankings incluye la métrica usada para ordenar. Para preguntas con varias partes devuelve en la "
        "misma consulta todas las columnas necesarias para responderlas. Puedes usar CTEs, subconsultas, tablas "
        "derivadas y funciones de ventana cuando simplifiquen el análisis. "
        "Para comparar un periodo con el anterior, primero agrega por periodo y luego usa LAG sobre la serie ordenada. "
        "Para encontrar el mejor periodo y compararlo con el anterior, conserva ambos valores y devuelve también la diferencia. "
        "Para un top N, calcula primero la métrica por entidad, ordénala y limita el resultado al N solicitado. "
        "Si además piden la diferencia entre posiciones del ranking, devuelve suficiente información para que Kenneth la calcule. "
        "Usa GROUP BY correctamente, evita JOIN innecesarios y termina con punto y coma. "
        + _dialect_rules()
    )


def generate_sql(question: str, history: list[dict] | None = None) -> str:
    database_context = get_compact_database_context()

    prompt = f"""ESQUEMA REAL:
{database_context}
{_history_text(history)}

PREGUNTA ACTUAL:
{question}
"""

    sql = ask_gemma(
        prompt,
        system=_sql_system_prompt(),
        temperature=0.0,
        num_predict=260,
    )

    if sql.startswith("```sql"):
        sql = sql[6:]
    if sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]

    return normalize_sql(sql.strip(), dialect=_active_dialect())


def repair_sql(
    question: str,
    failed_sql: str,
    error: str,
    history: list[dict] | None = None,
) -> str:
    """Hace un único intento de autocorrección cuando la primera consulta falla."""
    database_context = get_compact_database_context()
    prompt = f"""ESQUEMA REAL:
{database_context}
{_history_text(history)}

PREGUNTA ACTUAL:
{question}

SQL QUE FALLÓ:
{failed_sql}

ERROR DEVUELTO POR LA BASE:
{error[:1200]}

Corrige la consulta. Conserva todas las partes de la pregunta del usuario, usa alias claros y devuelve solo SQL.
Si la consulta era demasiado compleja como SELECT anidado, puedes reescribirla con WITH/CTEs y funciones de ventana.
"""

    sql = ask_gemma(
        prompt,
        system=_sql_system_prompt(),
        temperature=0.0,
        num_predict=280,
    )

    if sql.startswith("```sql"):
        sql = sql[6:]
    if sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]

    return normalize_sql(sql.strip(), dialect=_active_dialect())


def explain_results(
    question: str,
    sql: str,
    results: list[dict],
    history: list[dict] | None = None,
) -> str:
    prompt = f"""PREGUNTA ACTUAL:
{question}
{_history_text(history, limit=4)}

RESULTADOS REALES:
{results}

SQL EJECUTADO:
{sql}
"""

    return ask_gemma(
        prompt,
        system=(
            "Eres Kenneth, asistente empresarial. Responde en español de forma natural, directa y breve. "
            "Responde TODAS las partes de la pregunta usando exclusivamente los resultados recibidos. "
            "Puedes hacer aritmética simple entre valores que sí aparecen en los resultados, por ejemplo diferencias "
            "entre dos posiciones o dos meses. No inventes causas, datos, tendencias ni registros ausentes. "
            "Si falta algún valor necesario, dilo claramente. No muestres SQL salvo que lo pidan."
        ),
        temperature=0.1,
        num_predict=220,
    )

from ollama import chat

from app.ai.database_context import get_database_context
from app.ai.sql_normalizer import normalize_sql
from app.database.database_manager import database_manager


MODEL = "gemma3:4b"


def ask_gemma(prompt: str) -> str:
    response = chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.message.content


def _active_dialect() -> str:
    return database_manager.status().get("provider") or "sqlserver"


def _dialect_label() -> str:
    return "PostgreSQL" if _active_dialect() == "postgresql" else "Microsoft SQL Server"


def analyze_database(question: str) -> str:
    database_context = get_database_context()
    dialect_label = _dialect_label()

    prompt = f"""
Eres un asistente especializado en análisis de bases de datos empresariales.

A continuación recibirás la estructura real de una base de datos {dialect_label}.

ESTRUCTURA DE LA BASE DE DATOS:

{database_context}

Responde únicamente utilizando la información presente en ese esquema.

IMPORTANTE:
- No inventes tablas.
- No inventes columnas.
- Respeta las llaves primarias y foráneas.
- Interpreta correctamente la dirección de las relaciones.
- Si una tabla contiene una llave foránea hacia otra tabla, múltiples registros de la primera tabla pueden estar relacionados con un registro de la tabla referenciada.
- Si no puedes determinar algo a partir del esquema, indícalo.
- Responde en español.

PREGUNTA:

{question}
"""

    return ask_gemma(prompt)


def generate_sql(question: str) -> str:
    database_context = get_database_context()
    dialect = _active_dialect()
    dialect_label = _dialect_label()

    if dialect == "postgresql":
        dialect_rules = """
- La sintaxis debe ser exclusivamente PostgreSQL.
- Si necesitas limitar resultados usa LIMIT al final de la consulta.
- NUNCA uses TOP.
- Usa comillas dobles solo cuando necesites preservar mayúsculas/minúsculas o nombres especiales.
- Para fechas puedes usar EXTRACT, DATE_TRUNC y funciones nativas de PostgreSQL.
"""
    else:
        dialect_rules = """
- La sintaxis debe ser exclusivamente Microsoft SQL Server.
- Si necesitas limitar resultados usa TOP.
- NUNCA uses LIMIT.
- Para fechas usa funciones compatibles con SQL Server.
"""

    prompt = f"""
Eres un generador de consultas para {dialect_label}.

Debes generar UNA SOLA consulta que responda correctamente la pregunta del usuario.

ESTRUCTURA REAL DE LA BASE DE DATOS:

{database_context}

REGLAS OBLIGATORIAS:

1. Devuelve únicamente SQL plano.
2. NO uses bloques Markdown ni escribas ```sql.
3. Solo puedes usar SELECT.
4. No uses INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, EXEC, CREATE ni MERGE.
5. Usa únicamente tablas y columnas existentes en el esquema.
6. Respeta las llaves foráneas reales del esquema.
7. No inventes tablas, columnas o relaciones.
8. Usa únicamente los JOIN necesarios para responder la pregunta.
9. Para rankings, incluye en SELECT la métrica numérica utilizada para ordenar.
10. Para cantidades acumuladas usa SUM sobre una columna de cantidad apropiada cuando exista; no confundas cantidad con número de filas.
11. Para totales monetarios usa SUM sobre la columna monetaria que realmente represente el importe/total según el esquema.
12. Si una tabla ya contiene un total final de transacción, prefiere esa columna antes de reconstruirlo salvo que la pregunta requiera otro cálculo.
13. Distingue compras, ventas, pagos, inventario y otras operaciones según las tablas y relaciones reales; no mezcles procesos distintos.
14. Usa GROUP BY correctamente cuando agregues datos.
15. Termina la consulta con punto y coma.
16. No devuelvas únicamente nombres cuando exista una métrica relevante necesaria para responder la pregunta.
17. Si el esquema no permite responder con seguridad, genera la consulta más conservadora posible usando solo datos demostrables.

REGLAS DEL MOTOR:
{dialect_rules}

PREGUNTA:

{question}

RESPUESTA:
"""

    sql = ask_gemma(prompt).strip()

    if sql.startswith("```sql"):
        sql = sql[6:]
    if sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]

    return normalize_sql(sql, dialect=dialect)


def explain_results(
    question: str,
    sql: str,
    results: list[dict],
) -> str:
    prompt = f"""
Eres un asistente empresarial especializado en análisis de datos.

El usuario realizó la siguiente pregunta:

{question}

Para responderla se ejecutó esta consulta SQL:

{sql}

La base de datos devolvió estos resultados:

{results}

Explica los resultados al usuario de manera clara y breve.

REGLAS OBLIGATORIAS:
- Responde en español.
- Basa tu respuesta EXCLUSIVAMENTE en los valores presentes en los resultados.
- No inventes datos, porcentajes, cantidades, tendencias ni comparaciones.
- No calcules porcentajes si los valores necesarios para calcularlos no aparecen en los resultados.
- No afirmes que algo representa un porcentaje del total si el total no aparece en los resultados.
- No supongas cuántos registros existen fuera de los resultados recibidos.
- Si los resultados solo contienen nombres, limita tu respuesta a esos nombres y al orden en que aparecen.
- Si los resultados contienen una métrica numérica, puedes citarla y compararla.
- Si falta información para responder completamente la pregunta, indícalo claramente.
- Si no existen resultados, indícalo claramente.
- No inventes causas ni explicaciones que los datos no demuestren.
- Utiliza lenguaje empresarial comprensible.
- No muestres SQL salvo que el usuario lo solicite.
"""

    return ask_gemma(prompt)

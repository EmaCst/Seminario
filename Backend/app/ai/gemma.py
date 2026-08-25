from ollama import chat
from app.ai.sql_normalizer import normalize_sql

from app.ai.database_context import get_database_context


MODEL = "gemma3:4b"


def ask_gemma(prompt: str) -> str:
    response = chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.message.content


def analyze_database(question: str) -> str:
    database_context = get_database_context()

    prompt = f"""
Eres un asistente especializado en análisis de bases de datos empresariales.

A continuación recibirás la estructura real de una base de datos
Microsoft SQL Server.

ESTRUCTURA DE LA BASE DE DATOS:

{database_context}

Responde únicamente utilizando la información presente en ese esquema.

IMPORTANTE:
- No inventes tablas.
- No inventes columnas.
- Respeta las llaves primarias y foráneas.
- Interpreta correctamente la dirección de las relaciones.
- Si una tabla contiene una llave foránea hacia otra tabla, entonces
  múltiples registros de la primera tabla pueden estar relacionados
  con un registro de la tabla referenciada.
- Si no puedes determinar algo a partir del esquema, indícalo.
- Responde en español.

PREGUNTA:

{question}
"""

    return ask_gemma(prompt)


def generate_sql(question: str) -> str:
    database_context = get_database_context()

    prompt = f"""
Eres un generador de consultas para Microsoft SQL Server.

Debes generar UNA SOLA consulta SQL Server que responda
correctamente la pregunta del usuario.

ESTRUCTURA REAL DE LA BASE DE DATOS:

{database_context}

REGLAS OBLIGATORIAS:

1. Devuelve únicamente SQL plano.
2. NO uses bloques Markdown.
3. NO escribas ```sql ni ``` .
4. Solo puedes usar SELECT.
5. No uses INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE ni EXEC.
6. Usa únicamente tablas y columnas existentes en el esquema.
7. Respeta las llaves foráneas del esquema.
8. La sintaxis debe ser exclusivamente de Microsoft SQL Server.
9. Si necesitas limitar resultados usa TOP.
10. NUNCA uses LIMIT.
11. Para calcular productos más vendidos, usa SUM de la columna cantidad,
   no COUNT de registros.
12. Para totales monetarios, usa SUM sobre columnas monetarias apropiadas.
13. Si agrupas resultados, usa GROUP BY correctamente.
14. No inventes columnas, tablas o relaciones.
15. Termina la consulta con punto y coma.
16. Distingue estrictamente entre compras y ventas.
17. Si la pregunta habla de productos vendidos, ventas, clientes o ingresos,
    utiliza ventas y detalle_ventas.
18. No utilices compras ni detalle_compras para calcular ventas,
    salvo que la pregunta mencione explícitamente compras o proveedores.
19. Si la pregunta solicita productos más vendidos,
    calcula SUM(detalle_ventas.cantidad).
20. Usa únicamente las tablas necesarias para responder la pregunta.
    No agregues JOINs que no aporten información necesaria.
21. Si una tabla ya contiene una columna total que representa el total final
    de la transacción, usa esa columna en lugar de reconstruir el total.
22. Nunca sumes descuentos como si aumentaran el total; un descuento reduce el total.
23. Usa alias consistentes con el nombre de la tabla:
    v para ventas,
    dv para detalle_ventas,
    c para clientes,
    e para empleados,
    p para productos.
24. Cuando la pregunta solicite un ranking, incluye en el SELECT la métrica
    utilizada para ordenar los resultados.
25. Si ordenas productos por cantidad vendida, devuelve también
    SUM(detalle_ventas.cantidad) con un alias descriptivo.
26. Si ordenas clientes por dinero gastado, devuelve también SUM(ventas.total).
27. No devuelvas únicamente nombres si existe una métrica numérica relevante
    para responder la pregunta.

PREGUNTA:

{question}

RESPUESTA:
"""

    sql = ask_gemma(prompt).strip()

    # Limpieza defensiva por si Gemma ignora la regla de Markdown
    if sql.startswith("```sql"):
        sql = sql[6:]

    if sql.startswith("```"):
        sql = sql[3:]

    if sql.endswith("```"):
        sql = sql[:-3]

    return normalize_sql(sql)

def explain_results(
    question: str,
    sql: str,
    results: list[dict]
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
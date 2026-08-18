from ollama import chat

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
import requests

from app.ai.database_context import get_database_context


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:4b"


def main():

    print("\n===== OBTENIENDO ESQUEMA =====")

    database_context = get_database_context()

    print("Esquema obtenido correctamente.")

    prompt = f"""
Eres un asistente especializado en análisis de datos empresariales.

A continuación recibirás la estructura de una base de datos
Microsoft SQL Server.

ESTRUCTURA DE LA BASE DE DATOS:

{database_context}

Analiza únicamente la estructura proporcionada.

Responde la siguiente pregunta:

¿Qué tablas utilizarías para analizar las ventas de la empresa
y qué relación existe entre ellas?

No inventes tablas ni columnas que no aparezcan en el esquema.
Responde en español.
"""

    print("\n===== ENVIANDO ESQUEMA A GEMMA =====")

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )

    response.raise_for_status()

    data = response.json()

    print("\n===== RESPUESTA DE GEMMA =====")
    print(data["response"])


if __name__ == "__main__":
    main()
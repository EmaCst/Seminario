from ollama import chat

response = chat(
    model="gemma3:4b",
    messages=[
        {
            "role": "user",
            "content": "Explica en una frase qué es una base de datos empresarial."
        }
    ]
)

print(response.message.content)
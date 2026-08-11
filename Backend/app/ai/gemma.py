from ollama import chat


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
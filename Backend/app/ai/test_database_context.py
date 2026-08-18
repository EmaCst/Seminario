from app.ai.gemma import analyze_database


def main():
    question = (
        "¿Qué tablas utilizarías para analizar las ventas de la empresa "
        "y qué relación existe entre ellas?"
    )

    print("\n===== PREGUNTA =====")
    print(question)

    print("\n===== RESPUESTA DE GEMMA =====")

    response = analyze_database(question)

    print(response)


if __name__ == "__main__":
    main()
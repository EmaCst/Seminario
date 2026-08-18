from app.ai.gemma import generate_sql


def main():

    questions = [
        "¿Cuáles son los 5 productos más vendidos?",
        "¿Qué clientes han gastado más dinero?",
        "¿Cuánto se ha vendido por cada empleado?"
    ]

    for question in questions:

        print("\n======================================")
        print("PREGUNTA:")
        print(question)

        print("\nSQL GENERADO:")

        sql = generate_sql(question)

        print(sql)


if __name__ == "__main__":
    main()
from app.database.inspector import inspect_database
from app.database.serializer import schema_to_json


def main():
    print("\n===== INSPECCIONANDO BASE DE DATOS =====")

    schema = inspect_database()

    print(f"Base de datos: {schema.database}")
    print(f"Tablas detectadas: {len(schema.tables)}")
    print(f"Relaciones detectadas: {len(schema.relationships)}")

    print("\n===== JSON SERIALIZADO =====")

    json_schema = schema_to_json(schema)

    print(json_schema)


if __name__ == "__main__":
    main()
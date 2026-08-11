from sqlalchemy import inspect

from app.database.connection import engine


def inspect_database():

    inspector = inspect(engine)

    print("\n===== BASE DE DATOS =====")
    print("Seminario1")

    print("\n===== TABLAS =====")

    tables = inspector.get_table_names()

    for table in tables:
        print(f"\nTabla: {table}")

        columns = inspector.get_columns(table)

        for column in columns:
            print(
                f"  - {column['name']} "
                f"({column['type']})"
            )


if __name__ == "__main__":
    inspect_database()
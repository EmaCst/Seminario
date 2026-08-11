from app.database.connection import get_connection


def test_connection():

    with get_connection() as connection:

        result = connection.exec_driver_sql(
            "SELECT @@SERVERNAME AS servidor, DB_NAME() AS base_de_datos"
        )

        row = result.fetchone()

        print("Conexión exitosa")
        print(f"Servidor: {row.servidor}")
        print(f"Base de datos: {row.base_de_datos}")


if __name__ == "__main__":
    test_connection()   
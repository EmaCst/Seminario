from app.security.sql_validator import (
    SQLValidationError,
    validate_sql,
)


def test_query(sql: str):

    print("\n======================================")
    print("SQL:")
    print(sql)

    try:

        validate_sql(sql)

        print("RESULTADO: CONSULTA VÁLIDA")

    except SQLValidationError as error:

        print("RESULTADO: CONSULTA BLOQUEADA")
        print(f"MOTIVO: {error}")


def main():

    queries = [

        # Debe funcionar
        """
        SELECT TOP 5
            nombre
        FROM productos;
        """,

        # Tabla inexistente
        """
        SELECT *
        FROM productos_inventados;
        """,

        # JOIN válido
        """
        SELECT
            p.nombre,
            dv.cantidad
        FROM productos p
        JOIN detalle_ventas dv
            ON p.id = dv.producto_id;
        """,

        # JOIN con tabla inexistente
        """
        SELECT
            p.nombre
        FROM productos p
        JOIN tabla_falsa tf
            ON p.id = tf.producto_id;
        """,

        # Operación peligrosa
        """
        DELETE FROM productos;
        """,

        # Múltiples statements
        """
        SELECT *
        FROM clientes;

        DROP TABLE clientes;
        """
    ]

    for query in queries:
        test_query(query)


if __name__ == "__main__":
    main()
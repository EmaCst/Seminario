from app.database.query_executor import execute_query


def main():

    sql = """
    SELECT TOP 5
        p.nombre,
        p.precio_venta
    FROM productos p
    ORDER BY p.precio_venta DESC;
    """

    print("\n===== EJECUTANDO SQL =====")

    results = execute_query(sql)

    print("\n===== RESULTADOS =====")

    for row in results:
        print(row)


if __name__ == "__main__":
    main()
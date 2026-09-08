from datetime import datetime

from sqlalchemy import text

from app.analysis.semantic_mapper import inspect_semantic_map
from app.database.connection import get_connection


def get_total_sales() -> dict:
    semantic = inspect_semantic_map()["semantic_map"]

    sales = semantic["sales"]

    table = sales.get("header_table")
    total_column = sales.get("total_column")

    if not table or not total_column:
        return {
            "available": False,
            "value": None
        }

    sql = f"""
    SELECT
        COALESCE(SUM([{total_column}]), 0) AS total_sales
    FROM [{table}];
    """

    with get_connection() as connection:
        result = connection.execute(text(sql))
        row = result.mappings().first()

    return {
        "available": True,
        "value": float(row["total_sales"])
    }


def get_current_month_sales() -> dict:
    """
    Devuelve el total vendido en el mes y año actuales.
    """

    semantic = inspect_semantic_map()["semantic_map"]

    sales = semantic["sales"]

    table = sales.get("header_table")
    date_column = sales.get("date_column")
    total_column = sales.get("total_column")

    if not table or not date_column or not total_column:
        return {
            "available": False,
            "value": None
        }

    now = datetime.now()

    sql = f"""
    SELECT
        COALESCE(SUM([{total_column}]), 0) AS month_sales
    FROM [{table}]
    WHERE YEAR([{date_column}]) = :year
      AND MONTH([{date_column}]) = :month;
    """

    with get_connection() as connection:
        result = connection.execute(
            text(sql),
            {
                "year": now.year,
                "month": now.month
            }
        )

        row = result.mappings().first()

    return {
        "available": True,
        "value": float(row["month_sales"])
    }


def get_sales_count() -> dict:
    """
    Devuelve la cantidad total de ventas registradas.
    """

    semantic = inspect_semantic_map()["semantic_map"]

    sales = semantic["sales"]

    table = sales.get("header_table")

    if not table:
        return {
            "available": False,
            "value": None
        }

    sql = f"""
    SELECT
        COUNT(*) AS sales_count
    FROM [{table}];
    """

    with get_connection() as connection:
        result = connection.execute(text(sql))
        row = result.mappings().first()

    return {
        "available": True,
        "value": int(row["sales_count"])
    }


def get_average_ticket() -> dict:
    """
    Devuelve el valor promedio por venta.
    """

    semantic = inspect_semantic_map()["semantic_map"]

    sales = semantic["sales"]

    table = sales.get("header_table")
    total_column = sales.get("total_column")

    if not table or not total_column:
        return {
            "available": False,
            "value": None
        }

    sql = f"""
    SELECT
        COALESCE(AVG(CAST([{total_column}] AS DECIMAL(18,2))), 0)
            AS average_ticket
    FROM [{table}];
    """

    with get_connection() as connection:
        result = connection.execute(text(sql))
        row = result.mappings().first()

    return {
        "available": True,
        "value": float(row["average_ticket"])
    }


def get_sales_by_month() -> dict:
    semantic = inspect_semantic_map()["semantic_map"]

    sales = semantic["sales"]

    table = sales.get("header_table")
    date_column = sales.get("date_column")
    total_column = sales.get("total_column")

    if not table or not date_column or not total_column:
        return {
            "available": False,
            "data": []
        }

    sql = f"""
    SELECT
        YEAR([{date_column}]) AS year,
        MONTH([{date_column}]) AS month,
        SUM([{total_column}]) AS total
    FROM [{table}]
    WHERE [{date_column}] IS NOT NULL
    GROUP BY
        YEAR([{date_column}]),
        MONTH([{date_column}])
    ORDER BY
        YEAR([{date_column}]),
        MONTH([{date_column}]);
    """

    with get_connection() as connection:
        result = connection.execute(text(sql))
        rows = result.mappings().all()

    data = [
        {
            "year": row["year"],
            "month": row["month"],
            "total": float(row["total"])
        }
        for row in rows
    ]

    return {
        "available": True,
        "data": data
    }


def get_top_products(limit: int = 5) -> dict:
    semantic = inspect_semantic_map()["semantic_map"]

    sales = semantic["sales"]
    products = semantic["products"]

    detail_table = sales.get("detail_table")
    quantity_column = sales.get("quantity_column")

    product_table = products.get("table")
    product_name_column = products.get("name_column")

    product_relationship = sales.get(
        "product_relationship"
    )

    if (
        not detail_table
        or not quantity_column
        or not product_table
        or not product_name_column
        or not product_relationship
    ):
        return {
            "available": False,
            "data": []
        }

    detail_fk = product_relationship["from_column"]
    product_pk = product_relationship["to_column"]

    sql = f"""
    SELECT TOP {int(limit)}
        p.[{product_name_column}] AS product_name,
        SUM(d.[{quantity_column}]) AS quantity_sold
    FROM [{detail_table}] d
    INNER JOIN [{product_table}] p
        ON d.[{detail_fk}] = p.[{product_pk}]
    GROUP BY
        p.[{product_name_column}]
    ORDER BY
        quantity_sold DESC;
    """

    with get_connection() as connection:
        result = connection.execute(text(sql))
        rows = result.mappings().all()

    data = [
        {
            "product": row["product_name"],
            "quantity": int(row["quantity_sold"])
        }
        for row in rows
    ]

    return {
        "available": True,
        "data": data
    }


def get_dashboard_summary() -> dict:
    return {
        "total_sales": get_total_sales(),
        "current_month_sales": get_current_month_sales(),
        "sales_count": get_sales_count(),
        "average_ticket": get_average_ticket(),
        "sales_by_month": get_sales_by_month(),
        "top_products": get_top_products(),
        "critical_inventory": get_critical_inventory(),
        "top_customers": get_top_customers(),
        "sales_by_category": get_sales_by_category(),
    }

def get_critical_inventory() -> dict:
    """
    Devuelve productos cuyo stock actual es menor o igual
    al stock mínimo configurado.
    """

    semantic = inspect_semantic_map()["semantic_map"]

    inventory = semantic["inventory"]
    products = semantic["products"]

    inventory_table = inventory.get("table")
    stock_column = inventory.get("stock_column")
    minimum_column = inventory.get("minimum_column")

    product_table = products.get("table")
    product_name_column = products.get("name_column")

    product_relationship = inventory.get(
        "product_relationship"
    )

    if (
        not inventory_table
        or not stock_column
        or not minimum_column
        or not product_table
        or not product_name_column
        or not product_relationship
    ):
        return {
            "available": False,
            "data": []
        }

    inventory_fk = product_relationship["from_column"]
    product_pk = product_relationship["to_column"]

    sql = f"""
    SELECT
        p.[{product_name_column}] AS product_name,
        i.[{stock_column}] AS stock,
        i.[{minimum_column}] AS minimum_stock
    FROM [{inventory_table}] i
    INNER JOIN [{product_table}] p
        ON i.[{inventory_fk}] = p.[{product_pk}]
    WHERE i.[{stock_column}] <= i.[{minimum_column}]
    ORDER BY i.[{stock_column}] ASC;
    """

    with get_connection() as connection:
        result = connection.execute(text(sql))
        rows = result.mappings().all()

    data = [
        {
            "product": row["product_name"],
            "stock": int(row["stock"]),
            "minimum_stock": int(row["minimum_stock"])
        }
        for row in rows
    ]

    return {
        "available": True,
        "data": data
    }


def get_top_customers(limit: int = 5) -> dict:
    """
    Devuelve los clientes que más dinero han gastado.
    """

    semantic = inspect_semantic_map()["semantic_map"]

    sales = semantic["sales"]
    customers = semantic["customers"]

    sales_table = sales.get("header_table")
    total_column = sales.get("total_column")

    customer_table = customers.get("table")
    customer_name_column = customers.get("name_column")

    customer_relationship = sales.get(
        "customer_relationship"
    )

    if (
        not sales_table
        or not total_column
        or not customer_table
        or not customer_name_column
        or not customer_relationship
    ):
        return {
            "available": False,
            "data": []
        }

    sales_customer_fk = customer_relationship["from_column"]
    customer_pk = customer_relationship["to_column"]

    sql = f"""
    SELECT TOP {int(limit)}
        c.[{customer_name_column}] AS customer_name,
        SUM(v.[{total_column}]) AS total_spent
    FROM [{sales_table}] v
    INNER JOIN [{customer_table}] c
        ON v.[{sales_customer_fk}] = c.[{customer_pk}]
    GROUP BY
        c.[{customer_name_column}]
    ORDER BY
        total_spent DESC;
    """

    with get_connection() as connection:
        result = connection.execute(text(sql))
        rows = result.mappings().all()

    data = [
        {
            "customer": row["customer_name"],
            "total_spent": float(row["total_spent"])
        }
        for row in rows
    ]

    return {
        "available": True,
        "data": data
    }


def get_sales_by_category() -> dict:
    """
    Devuelve el total monetario vendido por categoría.

    Se calcula usando el detalle de ventas y el subtotal
    de cada línea, siempre que el mapper pueda identificarlo.
    """

    semantic_result = inspect_semantic_map()
    semantic = semantic_result["semantic_map"]

    sales = semantic["sales"]
    products = semantic["products"]
    categories = semantic["categories"]

    detail_table = sales.get("detail_table")

    product_table = products.get("table")
    category_table = categories.get("table")
    category_name_column = categories.get("name_column")

    product_relationship = sales.get(
        "product_relationship"
    )

    category_relationship = products.get(
        "category_relationship"
    )

    if (
        not detail_table
        or not product_table
        or not category_table
        or not category_name_column
        or not product_relationship
        or not category_relationship
    ):
        return {
            "available": False,
            "data": []
        }

    # Necesitamos encontrar una columna monetaria
    # dentro del detalle de ventas.
    from app.database.inspector import inspect_database

    schema = inspect_database()
    detail_schema = schema.tables.get(detail_table)

    if not detail_schema:
        return {
            "available": False,
            "data": []
        }

    detail_total_column = None

    preferred_columns = [
        "total",
        "subtotal",
        "importe",
        "amount"
    ]

    for preferred in preferred_columns:
        for column in detail_schema.columns:
            if column.name.lower() == preferred:
                detail_total_column = column.name
                break

        if detail_total_column:
            break

    if not detail_total_column:
        return {
            "available": False,
            "data": []
        }

    detail_product_fk = product_relationship["from_column"]
    product_pk = product_relationship["to_column"]

    product_category_fk = category_relationship["from_column"]
    category_pk = category_relationship["to_column"]

    sql = f"""
    SELECT
        c.[{category_name_column}] AS category_name,
        SUM(d.[{detail_total_column}]) AS total_sales
    FROM [{detail_table}] d
    INNER JOIN [{product_table}] p
        ON d.[{detail_product_fk}] = p.[{product_pk}]
    INNER JOIN [{category_table}] c
        ON p.[{product_category_fk}] = c.[{category_pk}]
    GROUP BY
        c.[{category_name_column}]
    ORDER BY
        total_sales DESC;
    """

    with get_connection() as connection:
        result = connection.execute(text(sql))
        rows = result.mappings().all()

    data = [
        {
            "category": row["category_name"],
            "total": float(row["total_sales"])
        }
        for row in rows
    ]

    return {
        "available": True,
        "data": data
    }
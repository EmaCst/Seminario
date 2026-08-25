from sqlalchemy import text

from app.analysis.semantic_mapper import inspect_semantic_map
from app.database.connection import get_connection


def get_total_sales() -> dict:
    """
    Devuelve el total acumulado de ventas.
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


def get_sales_by_month() -> dict:
    """
    Agrupa ventas por año y mes.
    """

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
    """
    Devuelve los productos más vendidos según cantidad.
    """

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

    detail_fk = product_relationship[
        "from_column"
    ]

    product_pk = product_relationship[
        "to_column"
    ]

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
    """
    Devuelve las métricas principales disponibles.
    """

    return {
        "total_sales": get_total_sales(),
        "sales_by_month": get_sales_by_month(),
        "top_products": get_top_products(),
    }
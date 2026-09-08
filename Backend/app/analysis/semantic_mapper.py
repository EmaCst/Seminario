from app.database.inspector import inspect_database
from app.database.schema import DatabaseSchema


def find_table_by_priority(
    schema: DatabaseSchema,
    exact_names: list[str],
    excluded_words: list[str] | None = None
) -> str | None:
    """
    Busca primero coincidencias exactas de nombre.
    Permite excluir tablas como detalle_ventas cuando buscamos ventas.
    """

    excluded_words = excluded_words or []

    tables = list(schema.tables.keys())

    # Primero coincidencia exacta
    for expected in exact_names:
        for table_name in tables:

            normalized = table_name.lower()

            if any(
                excluded in normalized
                for excluded in excluded_words
            ):
                continue

            if normalized == expected.lower():
                return table_name

    # Después coincidencia parcial
    for expected in exact_names:
        for table_name in tables:

            normalized = table_name.lower()

            if any(
                excluded in normalized
                for excluded in excluded_words
            ):
                continue

            if expected.lower() in normalized:
                return table_name

    return None


def find_column_by_priority(
    schema: DatabaseSchema,
    table_name: str,
    exact_names: list[str]
) -> str | None:
    """
    Busca columnas por prioridad.
    Primero coincidencia exacta.
    Después coincidencia parcial.
    """

    table = schema.tables.get(table_name)

    if not table:
        return None

    # Coincidencia exacta
    for expected in exact_names:
        for column in table.columns:

            if column.name.lower() == expected.lower():
                return column.name

    # Coincidencia parcial
    for expected in exact_names:
        for column in table.columns:

            if expected.lower() in column.name.lower():
                return column.name

    return None


def find_relationship(
    schema: DatabaseSchema,
    from_table: str,
    to_table: str
) -> dict | None:

    for relation in schema.relationships:

        if (
            relation.table == from_table
            and relation.references_table == to_table
        ):
            return {
                "from_table": relation.table,
                "from_column": relation.column,
                "to_table": relation.references_table,
                "to_column": relation.references_column,
            }

    return None


def build_semantic_map(
    schema: DatabaseSchema
) -> dict:

    semantic_map = {
        "sales": {},
        "products": {},
        "inventory": {},
        "customers": {},
        "employees": {},
        "payments": {},
        "purchases": {},
        "suppliers": {},
        "categories": {},
    }

    # ==========================================
    # SALES
    # ==========================================

    sales_header = find_table_by_priority(
        schema,
        [
            "ventas",
            "venta",
            "sales",
            "sale",
            "facturas",
            "factura",
            "invoices",
            "invoice",
            "orders",
            "order",
        ],
        excluded_words=[
            "detalle",
            "detail"
        ]
    )

    sales_detail = find_table_by_priority(
        schema,
        [
            "detalle_ventas",
            "detalleventa",
            "sales_detail",
            "sale_detail",
            "invoice_detail",
            "order_detail",
        ]
    )

    if sales_header:

        semantic_map["sales"]["header_table"] = sales_header

        semantic_map["sales"]["date_column"] = (
            find_column_by_priority(
                schema,
                sales_header,
                [
                    "fecha",
                    "date",
                    "created_at"
                ]
            )
        )

        semantic_map["sales"]["total_column"] = (
            find_column_by_priority(
                schema,
                sales_header,
                [
                    "total",
                    "monto_total",
                    "amount",
                    "monto"
                ]
            )
        )

    if sales_detail:

        semantic_map["sales"]["detail_table"] = sales_detail

        semantic_map["sales"]["quantity_column"] = (
            find_column_by_priority(
                schema,
                sales_detail,
                [
                    "cantidad",
                    "quantity",
                    "qty"
                ]
            )
        )

    # ==========================================
    # PRODUCTS
    # ==========================================

    product_table = find_table_by_priority(
        schema,
        [
            "productos",
            "producto",
            "products",
            "product",
            "items",
            "item",
        ]
    )

    if product_table:

        semantic_map["products"]["table"] = product_table

        semantic_map["products"]["name_column"] = (
            find_column_by_priority(
                schema,
                product_table,
                [
                    "nombre",
                    "name"
                ]
            )
        )

        semantic_map["products"]["price_column"] = (
            find_column_by_priority(
                schema,
                product_table,
                [
                    "precio_venta",
                    "sale_price",
                    "selling_price",
                    "precio",
                    "price"
                ]
            )
        )

    # ==========================================
    # INVENTORY
    # ==========================================

    inventory_table = find_table_by_priority(
        schema,
        [
            "inventario",
            "inventory",
            "stock",
            "existencias",
            "existencia",
        ]
    )

    if inventory_table:

        semantic_map["inventory"]["table"] = inventory_table

        semantic_map["inventory"]["stock_column"] = (
            find_column_by_priority(
                schema,
                inventory_table,
                [
                    "stock",
                    "cantidad",
                    "quantity",
                    "existencia"
                ]
            )
        )

        semantic_map["inventory"]["minimum_column"] = (
            find_column_by_priority(
                schema,
                inventory_table,
                [
                    "stock_minimo",
                    "min_stock",
                    "minimum_stock",
                    "minimo",
                    "minimum"
                ]
            )
        )

    # ==========================================
    # CUSTOMERS
    # ==========================================

    customer_table = find_table_by_priority(
        schema,
        [
            "clientes",
            "cliente",
            "customers",
            "customer",
            "clients",
            "client",
        ]
    )

    if customer_table:

        semantic_map["customers"]["table"] = customer_table

        semantic_map["customers"]["name_column"] = (
            find_column_by_priority(
                schema,
                customer_table,
                [
                    "nombre",
                    "name"
                ]
            )
        )

    # ==========================================
    # EMPLOYEES
    # ==========================================

    employee_table = find_table_by_priority(
        schema,
        [
            "empleados",
            "empleado",
            "employees",
            "employee",
            "staff",
        ]
    )

    if employee_table:

        semantic_map["employees"]["table"] = employee_table

        semantic_map["employees"]["name_column"] = (
            find_column_by_priority(
                schema,
                employee_table,
                [
                    "nombre",
                    "name"
                ]
            )
        )

    # ==========================================
    # PAYMENTS
    # ==========================================

    payment_table = find_table_by_priority(
        schema,
        [
            "pagos",
            "pago",
            "payments",
            "payment",
        ]
    )

    if payment_table:

        semantic_map["payments"]["table"] = payment_table

        semantic_map["payments"]["amount_column"] = (
            find_column_by_priority(
                schema,
                payment_table,
                [
                    "monto",
                    "amount",
                    "total"
                ]
            )
        )

        semantic_map["payments"]["method_column"] = (
            find_column_by_priority(
                schema,
                payment_table,
                [
                    "metodo",
                    "method"
                ]
            )
        )

    # ==========================================
    # PURCHASES
    # ==========================================

    purchase_header = find_table_by_priority(
        schema,
        [
            "compras",
            "compra",
            "purchases",
            "purchase",
        ],
        excluded_words=[
            "detalle",
            "detail"
        ]
    )

    if purchase_header:

        semantic_map["purchases"]["header_table"] = purchase_header

        semantic_map["purchases"]["date_column"] = (
            find_column_by_priority(
                schema,
                purchase_header,
                [
                    "fecha",
                    "date"
                ]
            )
        )

        semantic_map["purchases"]["total_column"] = (
            find_column_by_priority(
                schema,
                purchase_header,
                [
                    "total",
                    "monto_total",
                    "amount",
                    "monto"
                ]
            )
        )

    # ==========================================
    # SUPPLIERS
    # ==========================================

    supplier_table = find_table_by_priority(
        schema,
        [
            "proveedores",
            "proveedor",
            "suppliers",
            "supplier",
            "vendors",
            "vendor",
        ]
    )

    if supplier_table:

        semantic_map["suppliers"]["table"] = supplier_table

        semantic_map["suppliers"]["name_column"] = (
            find_column_by_priority(
                schema,
                supplier_table,
                [
                    "nombre",
                    "name"
                ]
            )
        )

    # ==========================================
    # CATEGORIES
    # ==========================================

    category_table = find_table_by_priority(
        schema,
        [
            "categorias",
            "categoria",
            "categories",
            "category",
        ]
    )

    if category_table:

        semantic_map["categories"]["table"] = category_table

        semantic_map["categories"]["name_column"] = (
            find_column_by_priority(
                schema,
                category_table,
                [
                    "nombre",
                    "name"
                ]
            )
        )

    # ==========================================
    # RELACIONES
    # ==========================================

    if sales_detail and product_table:

        relation = find_relationship(
            schema,
            sales_detail,
            product_table
        )

        if relation:
            semantic_map["sales"]["product_relationship"] = relation

    if sales_detail and sales_header:

        relation = find_relationship(
            schema,
            sales_detail,
            sales_header
        )

        if relation:
            semantic_map["sales"]["detail_relationship"] = relation

    if sales_header and customer_table:

        relation = find_relationship(
            schema,
            sales_header,
            customer_table
        )

        if relation:
            semantic_map["sales"]["customer_relationship"] = relation

    if sales_header and employee_table:

        relation = find_relationship(
            schema,
            sales_header,
            employee_table
        )

        if relation:
            semantic_map["sales"]["employee_relationship"] = relation

    if inventory_table and product_table:

        relation = find_relationship(
            schema,
            inventory_table,
            product_table
        )

        if relation:
            semantic_map["inventory"]["product_relationship"] = relation

    if product_table and category_table:

        relation = find_relationship(
            schema,
            product_table,
            category_table
        )

        if relation:
            semantic_map["products"]["category_relationship"] = relation

    return semantic_map


def inspect_semantic_map() -> dict:

    schema = inspect_database()

    semantic_map = build_semantic_map(schema)

    return {
        "database": schema.database,
        "semantic_map": semantic_map,
    }
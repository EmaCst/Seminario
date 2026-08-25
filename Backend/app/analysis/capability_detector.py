import re
import unicodedata

from app.database.inspector import inspect_database
from app.database.schema import DatabaseSchema


# ==========================================
# PALABRAS CLAVE POR DOMINIO
# ==========================================

CAPABILITY_KEYWORDS = {
    "sales": {
        "table_keywords": {
            "venta",
            "ventas",
            "sale",
            "sales",
            "factura",
            "facturas",
            "invoice",
            "invoices",
            "order",
            "orders",
            "pedido",
            "pedidos",
        },
        "column_keywords": {
            "total",
            "subtotal",
            "fecha",
            "date",
            "amount",
            "monto",
        },
    },

    "products": {
        "table_keywords": {
            "producto",
            "productos",
            "product",
            "products",
            "item",
            "items",
            "articulo",
            "articulos",
        },
        "column_keywords": {
            "nombre",
            "name",
            "precio",
            "price",
            "codigo",
            "code",
        },
    },

    "inventory": {
        "table_keywords": {
            "inventario",
            "inventory",
            "stock",
            "existencias",
            "existencia",
        },
        "column_keywords": {
            "stock",
            "cantidad",
            "quantity",
            "existencia",
            "existencias",
        },
    },

    "customers": {
        "table_keywords": {
            "cliente",
            "clientes",
            "customer",
            "customers",
            "client",
            "clients",
        },
        "column_keywords": {
            "nombre",
            "name",
            "correo",
            "email",
            "telefono",
            "phone",
        },
    },

    "employees": {
        "table_keywords": {
            "empleado",
            "empleados",
            "employee",
            "employees",
            "staff",
            "worker",
            "workers",
        },
        "column_keywords": {
            "nombre",
            "name",
            "puesto",
            "position",
            "salario",
            "salary",
        },
    },

    "payments": {
        "table_keywords": {
            "pago",
            "pagos",
            "payment",
            "payments",
        },
        "column_keywords": {
            "monto",
            "amount",
            "metodo",
            "method",
            "fecha",
            "date",
        },
    },

    "purchases": {
        "table_keywords": {
            "compra",
            "compras",
            "purchase",
            "purchases",
        },
        "column_keywords": {
            "total",
            "subtotal",
            "fecha",
            "date",
            "proveedor",
            "supplier",
        },
    },

    "suppliers": {
        "table_keywords": {
            "proveedor",
            "proveedores",
            "supplier",
            "suppliers",
            "vendor",
            "vendors",
        },
        "column_keywords": {
            "nombre",
            "name",
            "correo",
            "email",
            "telefono",
            "phone",
        },
    },
}


# ==========================================
# NORMALIZACIÓN
# ==========================================

def normalize_name(value: str) -> str:
    """
    Normaliza nombres para poder comparar:

    detalleVentas
    detalle_ventas
    Detalle Ventas

    de forma similar.
    """

    value = unicodedata.normalize("NFKD", value)

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    # Convierte camelCase en palabras separadas
    value = re.sub(
        r"([a-z0-9])([A-Z])",
        r"\1_\2",
        value
    )

    value = value.lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value
    )

    return value.strip("_")


def tokenize(value: str) -> set[str]:
    """
    Convierte un nombre en tokens.

    ejemplo:
    detalle_ventas -> {"detalle", "ventas"}
    """

    normalized = normalize_name(value)

    return {
        token
        for token in normalized.split("_")
        if token
    }


# ==========================================
# DETECCIÓN
# ==========================================

def table_matches_capability(
    table_name: str,
    column_names: list[str],
    capability: str
) -> bool:

    config = CAPABILITY_KEYWORDS[capability]

    table_tokens = tokenize(table_name)

    normalized_table = normalize_name(table_name)

    # --------------------------------------
    # COINCIDENCIA POR NOMBRE DE TABLA
    # --------------------------------------

    table_match = any(
        keyword in table_tokens
        or keyword == normalized_table
        for keyword in config["table_keywords"]
    )

    if not table_match:
        return False

    # --------------------------------------
    # COINCIDENCIA POR COLUMNAS
    # --------------------------------------

    column_tokens = set()

    for column_name in column_names:
        column_tokens.update(
            tokenize(column_name)
        )

    column_match_count = sum(
        1
        for keyword in config["column_keywords"]
        if keyword in column_tokens
    )

    # Basta con encontrar la tabla y al menos
    # una columna coherente con el dominio.
    return column_match_count >= 1


def detect_capabilities(
    schema: DatabaseSchema
) -> dict:

    capabilities = {}

    for capability in CAPABILITY_KEYWORDS:

        matched_tables = []

        for table_name, table in schema.tables.items():

            column_names = [
                column.name
                for column in table.columns
            ]

            if table_matches_capability(
                table_name,
                column_names,
                capability
            ):
                matched_tables.append(
                    table_name
                )

        capabilities[capability] = {
            "available": len(matched_tables) > 0,
            "tables": matched_tables,
        }

    return capabilities


def inspect_capabilities() -> dict:
    """
    Inspecciona la BD actual y detecta
    qué capacidades empresariales existen.
    """

    schema = inspect_database()

    capabilities = detect_capabilities(
        schema
    )

    return {
        "database": schema.database,
        "capabilities": capabilities,
    }
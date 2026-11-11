"""Regression coverage for generic retail schema detection (no DB required)."""
import unittest

from app.analysis.semantic_mapper import build_semantic_map
from app.database.schema import (
    ColumnSchema,
    DatabaseSchema,
    RelationshipSchema,
    TableSchema,
)


def table(name, *columns):
    return TableSchema(name=name, columns=[
        ColumnSchema(name=column, type="nvarchar", nullable=False)
        for column in columns
    ])


class RetailSchemaMappingTests(unittest.TestCase):
    def test_spanish_pedidos_with_relations(self):
        schema = DatabaseSchema(
            database="MercadoGlobalDB",
            tables={
                "Pedidos": table("Pedidos", "PedidoID", "ClienteID", "FechaPedido", "Total"),
                "DetallesPedido": table("DetallesPedido", "DetalleID", "PedidoID", "ProductoID", "Cantidad", "ImporteNeto"),
                "Productos": table("Productos", "ProductoID", "CategoriaID", "Nombre", "PrecioLista"),
                "Clientes": table("Clientes", "ClienteID", "Nombre", "Apellido"),
                "Categorias": table("Categorias", "CategoriaID", "Nombre"),
                "Inventario": table("Inventario", "ProductoID", "StockActual", "StockMinimo"),
            },
            relationships=[
                RelationshipSchema("DetallesPedido", "PedidoID", "Pedidos", "PedidoID"),
                RelationshipSchema("DetallesPedido", "ProductoID", "Productos", "ProductoID"),
                RelationshipSchema("Pedidos", "ClienteID", "Clientes", "ClienteID"),
                RelationshipSchema("Productos", "CategoriaID", "Categorias", "CategoriaID"),
                RelationshipSchema("Inventario", "ProductoID", "Productos", "ProductoID"),
            ],
        )
        mapping = build_semantic_map(schema)
        sales = mapping["sales"]
        self.assertEqual(sales["header_table"], "Pedidos")
        self.assertEqual(sales["detail_table"], "DetallesPedido")
        self.assertEqual(sales["date_column"], "FechaPedido")
        self.assertEqual(sales["total_column"], "Total")
        self.assertEqual(sales["quantity_column"], "Cantidad")
        self.assertEqual(sales["detail_relationship"]["from_column"], "PedidoID")
        self.assertEqual(sales["product_relationship"]["from_column"], "ProductoID")
        self.assertEqual(sales["customer_relationship"]["from_column"], "ClienteID")
        self.assertEqual(mapping["products"]["category_relationship"]["from_column"], "CategoriaID")
        self.assertEqual(mapping["inventory"]["minimum_column"], "StockMinimo")

    def test_existing_english_orders_remain_supported(self):
        schema = DatabaseSchema(
            database="Store",
            tables={
                "Orders": table("Orders", "Id", "created_at", "total"),
                "Order_Detail": table("Order_Detail", "order_id", "product_id", "quantity"),
                "Products": table("Products", "product_id", "name"),
            },
        )
        mapping = build_semantic_map(schema)
        self.assertEqual(mapping["sales"]["header_table"], "Orders")
        self.assertEqual(mapping["sales"]["detail_table"], "Order_Detail")
        self.assertEqual(mapping["sales"]["quantity_column"], "quantity")

    def test_orders_not_confused_with_detail(self):
        schema = DatabaseSchema(
            database="Store",
            tables={
                "Detalle_Pedido": table("Detalle_Pedido", "PedidoID", "Cantidad"),
                "Pedido": table("Pedido", "PedidoID", "Fecha", "Total"),
            },
        )
        mapping = build_semantic_map(schema)
        self.assertEqual(mapping["sales"]["header_table"], "Pedido")
        self.assertEqual(mapping["sales"]["detail_table"], "Detalle_Pedido")


if __name__ == "__main__":
    unittest.main()

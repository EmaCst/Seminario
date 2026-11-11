"""End-to-end checks for commerce chat requests and verified joined queries."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, text

from app.visualizations import conversational_drafts as chat
from app.visualizations import visualization_service as visual


def field(key, kind="number", semantic=None, identifier=False):
    return {
        "key": key, "label": key, "kind": kind, "semantic": semantic,
        "is_identifier": identifier, "aggregations": ["sum", "avg", "count", "max", "min"],
    }


def entity(role, table, pk, columns):
    return {
        "key": role, "semantic_role": role, "table": table, "label": table,
        "primary_key": [pk], "fields": columns,
        "dimensions": [x for x in columns if x["kind"] in ("text", "date")],
        "metrics": [x for x in columns if x["kind"] == "number"],
    }


def commerce_fixture():
    customers = entity("customers", "Clientes", "ClienteID", [
        field("ClienteID", identifier=True), field("Nombre", "text", "name"),
        field("Apellido", "text"),
    ])
    sales = entity("orders", "Pedidos", "PedidoID", [
        field("PedidoID", identifier=True), field("ClienteID", identifier=True),
        field("FechaPedido", "date", "date"), field("Total", semantic="total"),
    ])
    details = entity("order_details", "DetallesPedido", "DetalleID", [
        field("DetalleID", identifier=True), field("PedidoID", identifier=True),
        field("ProductoID", identifier=True), field("Cantidad", semantic="quantity"),
        field("ImporteNeto"), field("ImporteBruto"),
    ])
    products = entity("products", "Productos", "ProductoID", [
        field("ProductoID", identifier=True), field("CategoriaID", identifier=True),
        field("Nombre", "text", "name"),
    ])
    categories = entity("categories", "Categorias", "CategoriaID", [
        field("CategoriaID", identifier=True), field("Nombre", "text", "name"),
    ])
    relations = [
        ("Pedidos", "ClienteID", "Clientes", "ClienteID"),
        ("DetallesPedido", "PedidoID", "Pedidos", "PedidoID"),
        ("DetallesPedido", "ProductoID", "Productos", "ProductoID"),
        ("Productos", "CategoriaID", "Categorias", "CategoriaID"),
    ]
    catalog = {
        "database": "commerce", "domain": "retail",
        "entities": [sales, details, products, categories, customers],
        "relationships": [
            {"from_table": a, "from_column": b, "to_table": c, "to_column": d}
            for a, b, c, d in relations
        ],
    }
    schema = SimpleNamespace(
        tables={
            item["table"]: SimpleNamespace(
                name=item["table"], primary_key=item["primary_key"],
                columns=[
                    SimpleNamespace(name=col["key"],
                                    type=("DATETIME" if col["kind"] == "date" else
                                          "NVARCHAR" if col["kind"] == "text" else "DECIMAL"))
                    for col in item["fields"]
                ],
            ) for item in catalog["entities"]
        },
        relationships=[
            SimpleNamespace(table=a, column=b, references_table=c, references_column=d)
            for a, b, c, d in relations
        ],
    )
    return catalog, schema


PRODUCTS_PROMPT = (
    "Crea una gráfica de barras con los 10 productos más vendidos por unidades, "
    "mostrando el nombre de cada producto y su cantidad total vendida."
)
CATEGORIES_PROMPT = (
    "Genera una gráfica circular mostrando qué porcentaje de las ventas netas "
    "corresponde a cada categoría de productos."
)
CUSTOMERS_PROMPT = (
    "Crea una tabla con los 20 clientes que más han comprado, incluyendo nombre "
    "completo, cantidad de pedidos, total gastado, ticket promedio y fecha de su última compra."
)
GROWTH_PROMPT = (
    "Analiza las ventas mensuales durante los últimos dos años, identifica los "
    "tres meses con mayores ingresos y calcula el crecimiento porcentual de "
    "las ventas respecto al mes anterior. Muéstralo en una tabla."
)


class CommerceConversationTests(unittest.TestCase):
    def setUp(self):
        self.catalog, self.schema = commerce_fixture()

    def draft(self, prompt):
        with patch.object(chat, "get_semantic_visualization_catalog",
                          return_value=self.catalog), \
             patch("app.database.inspector.inspect_database", return_value=self.schema), \
             patch.object(chat, "preview_visualization", return_value={
                 "data": [{"dimension": "Ejemplo", "value": 5}], "meta": {}
             }), \
             patch.object(chat.database_manager, "status",
                          return_value={"provider": "sqlserver", "database": "commerce"}), \
             patch.object(chat, "_source_key", return_value="sqlserver:commerce"):
            return chat.interpret_visualization_request(prompt)

    def sql(self, definition):
        with patch.object(visual, "inspect_database", return_value=self.schema), \
             patch.object(visual.database_manager, "status",
                          return_value={"provider": "sqlserver"}):
            return visual.build_visualization_query(
                visual.VisualizationDefinition.model_validate(definition)
            )

    def test_products_use_line_quantity_and_product_name(self):
        definition = self.draft(PRODUCTS_PROMPT)["definition"]
        self.assertEqual("DetallesPedido", definition["table"])
        self.assertEqual("Cantidad", definition["metric"])
        self.assertEqual("Productos", definition["group_by_table"])
        self.assertEqual("Nombre", definition["group_by"])
        self.assertEqual(10, definition["limit"])
        sql = self.sql(definition)
        self.assertIn("SUM([DetallesPedido].[Cantidad])", sql)
        self.assertIn("LEFT JOIN [Productos]", sql)
        self.assertIn("TOP 10", sql)

    def test_category_share_joins_two_verified_parents(self):
        definition = self.draft(CATEGORIES_PROMPT)["definition"]
        self.assertEqual("donut", definition["visualization"])
        self.assertEqual("ImporteNeto", definition["metric"])
        self.assertTrue(definition["percentage_share"])
        sql = self.sql(definition)
        self.assertIn("LEFT JOIN [Productos]", sql)
        self.assertIn("LEFT JOIN [Categorias]", sql)
        self.assertIn("SUM(value) OVER ()", sql)
        self.assertNotIn("ImporteBruto", sql)

    def test_customer_ranking_has_correct_order_and_multiple_metrics(self):
        definition = self.draft(CUSTOMERS_PROMPT)["definition"]
        self.assertEqual("Pedidos", definition["table"])
        self.assertEqual("Total", definition["metric"])
        self.assertEqual(20, definition["limit"])
        self.assertEqual("Apellido", definition["group_by_extra"])
        self.assertEqual(["count", "avg", "max"],
                         [m["aggregation"] for m in definition["additional_metrics"]])
        sql = self.sql(definition)
        self.assertIn("COUNT(*) AS extra_0", sql)
        self.assertIn("AVG([Pedidos].[Total]) AS extra_1", sql)
        self.assertIn("MAX([Pedidos].[FechaPedido]) AS extra_2", sql)
        self.assertIn("LEFT JOIN [Clientes]", sql)
        self.assertIn("TOP 20", sql)

    def test_growth_calculated_before_top_three(self):
        self.assertTrue(chat.is_visualization_creation_request(GROWTH_PROMPT))
        definition = self.draft(GROWTH_PROMPT)["definition"]
        self.assertEqual("month", definition["time_granularity"])
        self.assertTrue(definition["period_growth"])
        self.assertTrue(definition["rank_periods"])
        self.assertEqual(3, definition["limit"])
        sql = self.sql(definition)
        self.assertIn("LAG(value) OVER (ORDER BY dimension)", sql)
        self.assertIn("AS monthly", sql)
        self.assertIn("TOP 3", sql)
        self.assertIn("ORDER BY value DESC", sql)

    def test_unverified_join_is_not_guessed(self):
        self.catalog["relationships"] = []
        with self.assertRaisesRegex(ValueError, "tabla de líneas"):
            self.draft(PRODUCTS_PROMPT)

    def test_actual_sqlite_aggregates_have_correct_grain_and_growth(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        try:
            with engine.begin() as c:
                c.execute(text('CREATE TABLE "Pedidos" ("PedidoID" INT, "ClienteID" INT, "FechaPedido" TEXT, "Total" NUMERIC)'))
                for order in [
                    (1, 1, "2026-01-05", 100), (2, 1, "2026-01-12", 100),
                    (3, 2, "2026-02-05", 300), (4, 2, "2026-03-05", 150),
                ]:
                    c.execute(text('INSERT INTO "Pedidos" VALUES (:id,:client,:date,:total)'), dict(
                        id=order[0], client=order[1], date=order[2], total=order[3]))
            definition = visual.VisualizationDefinition(
                title="Cambio mensual", visualization="table",
                table="Pedidos", metric="Total", aggregation="sum",
                group_by="FechaPedido", time_granularity="month",
                period_growth=True, rank_periods=True, limit=3,
            )
            with patch.object(visual, "inspect_database", return_value=self.schema), \
                 patch.object(visual.database_manager, "status",
                              return_value={"provider": "excel"}):
                sql = visual.build_visualization_query(definition)
            with engine.connect() as c:
                rows = c.execute(text(sql)).mappings().all()
            self.assertEqual(["2026-02", "2026-01", "2026-03"],
                             [row["dimension"] for row in rows])
            self.assertEqual(50.0, float(rows[0]["growth_percent"]))
            self.assertIsNone(rows[1]["growth_percent"])
            self.assertEqual(-50.0, float(rows[2]["growth_percent"]))
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

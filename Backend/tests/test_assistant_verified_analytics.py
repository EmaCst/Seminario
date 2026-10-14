"""Regression cases for conversational business questions, using SQLite fixtures."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine

from app.services import assistant_analytics as analytics
from app.services.assistant_router import route_request


SEMANTIC = {
    "sales": {
        "header_table": "ventas", "date_column": "fecha", "total_column": "total",
        "detail_table": "detalle_ventas", "quantity_column": "cantidad",
        "detail_relationship": {"from_column": "venta_id", "to_column": "id"},
        "product_relationship": {"from_column": "producto_id", "to_column": "id"},
        "customer_relationship": {"from_column": "cliente_id", "to_column": "id"},
    },
    "products": {"table": "productos", "name_column": "nombre"},
    "customers": {"table": "clientes", "name_column": "nombre"},
}


class RouterTests(unittest.TestCase):
    def test_greetings_and_typos(self):
        for greeting in ("hola", "hola keneth", "hola kenneth", "holi kenteh", "buenas tardes"):
            with self.subTest(greeting=greeting):
                self.assertEqual("conversation", route_request(greeting).kind)
        self.assertEqual("monthly_total", route_request("Hola, dime las ventas de junio").kind)

    def test_specific_entity_over_monthly_sales(self):
        self.assertEqual("product_top", route_request("dime el producto más vendido de junio").kind)
        self.assertEqual("customer_top", route_request("dime nuestro meyor cliente").kind)
        self.assertEqual("monthly_total", route_request("dime las ventas de junio").kind)
        self.assertEqual("count", route_request("¿cuántas ventas hubo en junio?").metric)

    def test_product_attribution_recovers_months(self):
        previous = [{"role": "user", "content": "ventas de junio frente a febrero"}]
        followup = route_request("¿qué producto marcó esa diferencia?", previous)
        self.assertEqual("product_attribution", followup.kind)
        self.assertEqual({2, 6}, set(followup.months))

    def test_short_followup_recovers_months(self):
        previous = [{"role": "user", "content": "dime la diferencia entre junio y febrero"}]
        followup = route_request("¿y cuál fue la diferencia entre los dos meses?", previous)
        self.assertEqual("monthly_compare", followup.kind)
        self.assertEqual({2, 6}, set(followup.months))

    def test_greeting_stops_old_context(self):
        previous = [
            {"role": "user", "content": "ventas de junio y febrero"},
            {"role": "user", "content": "hola"},
        ]
        followup = route_request("¿cuál fue la diferencia entre los dos meses?", previous)
        self.assertEqual("sql", followup.kind)


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        with self.engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE productos(id INTEGER PRIMARY KEY, nombre TEXT)")
            connection.exec_driver_sql("CREATE TABLE clientes(id INTEGER PRIMARY KEY, nombre TEXT)")
            connection.exec_driver_sql("CREATE TABLE ventas(id INTEGER PRIMARY KEY, fecha TEXT, total REAL, cliente_id INTEGER)")
            connection.exec_driver_sql("CREATE TABLE detalle_ventas(id INTEGER PRIMARY KEY, venta_id INTEGER, producto_id INTEGER, cantidad INTEGER, subtotal REAL)")
            connection.exec_driver_sql("INSERT INTO productos VALUES(1,'Café'),(2,'Pan')")
            connection.exec_driver_sql("INSERT INTO clientes VALUES(1,'Ana'),(2,'Luis')")
            connection.exec_driver_sql("INSERT INTO ventas VALUES(1,'2026-02-03',100,1),(2,'2026-06-03',300,1),(3,'2026-06-04',200,2)")
            connection.exec_driver_sql("INSERT INTO detalle_ventas VALUES(1,1,1,1,100),(2,2,1,3,300),(3,3,2,2,200)")
        schema = SimpleNamespace(tables={"detalle_ventas": SimpleNamespace(columns=[
            SimpleNamespace(name="id"), SimpleNamespace(name="venta_id"),
            SimpleNamespace(name="producto_id"), SimpleNamespace(name="cantidad"),
            SimpleNamespace(name="subtotal"),
        ])})
        self.patches = [
            patch.object(analytics, "_sales_model", return_value=SEMANTIC),
            patch.object(analytics, "_provider", return_value="excel"),
            patch.object(analytics, "_quote", side_effect=lambda identifier: '"' + identifier.replace('"', '""') + '"'),
            patch.object(analytics, "get_connection", side_effect=lambda: self.engine.connect()),
            patch("app.database.inspector.inspect_database", return_value=schema),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.engine.dispose()

    def test_amount_vs_count(self):
        amount = analytics.run_verified_analytics(route_request("ventas de junio"))
        count = analytics.run_verified_analytics(route_request("cuántas ventas en junio"))
        self.assertIn("500.00", amount["answer"])
        self.assertIn("2 transacciones", count["answer"])

    def test_month_difference(self):
        result = analytics.run_verified_analytics(route_request("diferencia entre ventas junio y febrero"))
        self.assertIn("400.00", result["answer"])
        self.assertEqual("analytics", result["mode"])

    def test_top_product_by_units(self):
        result = analytics.run_verified_analytics(route_request("producto más vendido de junio"))
        self.assertIn("Café", result["answer"])
        self.assertIn("3 unidades", result["answer"])

    def test_top_customer_by_revenue(self):
        result = analytics.run_verified_analytics(route_request("nuestro meyor cliente"))
        self.assertIn("Ana", result["answer"])
        self.assertIn("400.00", result["answer"])

    def test_attribution_uses_line_totals(self):
        history = [{"role": "user", "content": "diferencia en ventas de junio y febrero"}]
        intent = route_request("qué producto marcó esa diferencia", history)
        result = analytics.run_verified_analytics(intent)
        self.assertIn("Pan", result["answer"])  # +200 vs Cafe +200; tie is valid
        self.assertEqual(2, len(result["data"]))

    def test_missing_relation_is_not_fabricated(self):
        bad = {key: dict(value) for key, value in SEMANTIC.items()}
        bad["sales"].pop("customer_relationship")
        with patch.object(analytics, "_sales_model", return_value=bad):
            result = analytics.run_verified_analytics(route_request("mejor cliente"))
        self.assertIn("falta una relación", result["answer"])


if __name__ == "__main__":
    unittest.main()

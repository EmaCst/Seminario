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
        self.assertEqual("product_top", route_request("el produtco mas vendido de junio").kind)
        self.assertEqual("customer_top", route_request("nuestro mejor clietne").kind)
        self.assertEqual("count", route_request("cliente con mas compras").metric)
        self.assertEqual("count", route_request("¿cuántas ventas hubo en junio?").metric)

    def test_product_attribution_recovers_months(self):
        previous = [{"role": "user", "content": "ventas de junio frente a febrero"}]
        followup = route_request("¿qué producto marcó esa diferencia?", previous)
        self.assertEqual("product_attribution", followup.kind)
        self.assertEqual({2, 6}, set(followup.months))

    def test_explicit_new_period_does_not_inherit_unrelated_year(self):
        history = [{"role": "user", "content": "ventas de febrero de 2024"}]
        intent = route_request("ventas de junio", history)
        self.assertIsNone(intent.year)

    def test_followup_changes_period_not_measure(self):
        history = [{"role": "user", "content": "producto más vendido de junio"}]
        intent = route_request("¿y en febrero?", history)
        self.assertEqual("product_top", intent.kind)
        self.assertEqual("units", intent.metric)
        self.assertEqual((2,), intent.months)
        history = [{"role": "user", "content": "pronostica las ventas de los próximos meses"}]
        self.assertEqual("forecast", route_request("¿y para 6 meses?", history).kind)

    def test_top_n_count_is_bounded(self):
        self.assertEqual(3, route_request("top 3 productos").limit)
        self.assertEqual(20, route_request("top 99 clientes").limit)

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
            connection.exec_driver_sql("INSERT INTO ventas VALUES(1,'2026-02-03',100,1),(2,'2026-06-03',290,1),(3,'2026-06-04',210,2)")
            connection.exec_driver_sql("INSERT INTO detalle_ventas VALUES(1,1,1,1,100),(2,2,1,3,290),(3,3,2,2,210)")
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

    def test_units_sold_are_not_invoice_counts(self):
        result = analytics.run_verified_analytics(route_request("unidades vendidas de junio"))
        self.assertIn("5", result["answer"])
        self.assertIn("se vendieron 5 unidades", result["answer"])

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
        self.assertIn("390.00", result["answer"])

    def test_attribution_uses_line_totals(self):
        history = [{"role": "user", "content": "diferencia en ventas de junio y febrero"}]
        intent = route_request("qué producto marcó esa diferencia", history)
        result = analytics.run_verified_analytics(intent)
        self.assertIn("Pan", result["answer"])  # +210 vs Café +190
        self.assertEqual(2, len(result["data"]))

    def test_ranking_top_n_and_month_filter(self):
        ranked = analytics.run_verified_analytics(route_request("top 2 productos de junio"))
        self.assertEqual(2, len(ranked["data"]))
        self.assertIn("Café", ranked["answer"])
        customers = analytics.run_verified_analytics(route_request("top 2 clientes"))
        self.assertEqual(2, len(customers["data"]))
        monthly = analytics.run_verified_analytics(route_request("mejor cliente de junio"))
        self.assertIn("290.00", monthly["answer"])
        self.assertNotIn("390.00", monthly["answer"])

    def test_conversation_end_to_end_never_calls_gemma_for_supported_intents(self):
        from app.services.assistant_service import ask_database

        with patch("app.services.assistant_service.generate_sql",
                   side_effect=AssertionError("This intent must not reach Gemma")):
            greeting = ask_database("hola keneth")
            self.assertEqual("conversation", greeting["mode"])

            june = ask_database("dime las ventas de junio")
            self.assertIn("500.00", june["answer"])

            comparison = ask_database("diferencia entre ventas de junio y febrero")
            self.assertIn("400.00", comparison["answer"])

            history = [
                {"role": "user", "content": "diferencia entre ventas de junio y febrero"},
                {"role": "assistant", "content": comparison["answer"]},
            ]
            followup = ask_database("y cuál fue el producto que marcó esa diferencia?", history)
            self.assertIn("Pan", followup["answer"])

            product = ask_database("dime el producto más vendido de junio")
            self.assertIn("Café", product["answer"])

            customer = ask_database("dime nuestro meyor cliente")
            self.assertIn("Ana", customer["answer"])

    def test_analytic_failure_does_not_fall_back_to_unrelated_sql(self):
        from app.services.assistant_service import ask_database
        with patch.object(analytics, "_query", side_effect=RuntimeError("database offline")):
            with patch("app.services.assistant_service.generate_sql",
                       side_effect=AssertionError("Do not fabricate another query")):
                # The simulated failure must be logged, but it should not print a
                # confusing stack trace during a successful regression test.
                with patch("logging.Logger.exception") as logged_exception:
                    result = ask_database("dime las ventas de junio")
        logged_exception.assert_called_once()
        self.assertEqual("error", result["mode"])
        self.assertIn("No pude consultar", result["answer"])

    def test_missing_relation_is_not_fabricated(self):
        bad = {key: dict(value) for key, value in SEMANTIC.items()}
        bad["sales"].pop("customer_relationship")
        with patch.object(analytics, "_sales_model", return_value=bad):
            result = analytics.run_verified_analytics(route_request("mejor cliente"))
        self.assertIn("falta una relación", result["answer"])


if __name__ == "__main__":
    unittest.main()

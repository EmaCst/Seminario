"""Phase 3: business-chat drafts are validated, dated, editable and never saved.

python -m unittest discover -s tests -p 'test_conversational_visualizations.py' -v
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, text

from app.services import assistant_service
from app.visualizations import conversational_drafts as draft
from app.visualizations import visualization_service as visual


def catalog(role="sales", name="Ventas", table="ventas", *, include_amount=True,
            include_date=True, multiple_amounts=False):
    fields = [
        {"key": "estado", "label": "Estado", "kind": "text", "semantic": "status",
         "dimension": True, "filter": True},
    ]
    if include_date:
        fields.append({"key": "fecha", "label": "Fecha", "kind": "date", "semantic": "date",
                       "dimension": True, "filter": True})
    if include_amount:
        fields.append({"key": "total", "label": "Total", "kind": "number", "semantic": "total",
                       "metric": True, "aggregations": ["sum", "avg", "min", "max", "count"]})
    if multiple_amounts:
        fields.append({"key": "monto", "label": "Monto", "kind": "number", "semantic": "amount",
                       "metric": True, "aggregations": ["sum", "avg", "count"]})
    return {
        "database": "empresa",
        "domain": "retail" if role == "sales" else "healthcare",
        "entities": [{
            "key": role, "semantic_role": role, "label": name, "table": table,
            "fields": fields,
            "metrics": [field for field in fields if field.get("metric")],
            "dimensions": [field for field in fields if field.get("dimension")],
            "filters": [field for field in fields if field.get("filter")],
        }],
        "relationships": [],
    }


def fake_preview(definition):
    return {
        "definition": definition.model_dump(),
        "data": [{"dimension": "2026-01", "value": 123.5},
                 {"dimension": "2026-02", "value": 132}],
        "meta": {"rows": 2, "provider": "excel"},
    }


class ConversationDraftTests(unittest.TestCase):
    def _interpret(self, question, data=None):
        with patch.object(draft, "get_semantic_visualization_catalog",
                          return_value=data or catalog()):
            with patch.object(draft, "preview_visualization", side_effect=fake_preview):
                with patch.object(draft.database_manager, "status",
                                  return_value={"provider": "excel", "database": "empresa"}):
                    with patch.object(draft, "_source_key", return_value="excel:empresa"):
                        return draft.interpret_visualization_request(question)

    def test_explicit_creation_intent_but_not_chart_explanation(self):
        self.assertTrue(draft.is_visualization_creation_request(
            "Crea una gráfica de barras con las ventas por mes de 2026 y agrégala al dashboard"))
        self.assertTrue(draft.is_visualization_creation_request(
            "Haz una tabla de citas por estado"))
        self.assertFalse(draft.is_visualization_creation_request(
            "¿Cómo crear una gráfica de barras?"))
        self.assertFalse(draft.is_visualization_creation_request(
            "¿Por qué bajaron las ventas en diciembre?"))

    def test_engineer_example_is_monthly_and_stays_unpublished(self):
        result = self._interpret(
            "Crea una gráfica de barras con las ventas por mes de 2026 y agrégala al dashboard"
        )
        config = result["definition"]
        self.assertEqual("bar", config["visualization"])
        self.assertEqual("ventas", config["table"])
        self.assertEqual("total", config["metric"])
        self.assertEqual("sum", config["aggregation"])
        self.assertEqual("fecha", config["group_by"])
        self.assertEqual("month", config["time_granularity"])
        self.assertEqual([
            ("gte", "2026-01-01"), ("lt", "2027-01-01"),
        ], [(p["operator"], p["value"]) for p in config["filters"]])
        self.assertEqual({"dashboard": True, "analytics": False}, result["placement"])
        self.assertEqual("2026-01", result["preview"]["data"][0]["dimension"])
        self.assertEqual("ready", result["status"])
        self.assertEqual("excel:empresa", result["source"]["key"])

    def test_table_by_status_can_open_existing_builder(self):
        result = self._interpret(
            "Haz una tabla con las citas por estado para 2026 en analítica",
            catalog("appointments", "Citas", "citas", include_amount=False),
        )
        self.assertEqual("table", result["definition"]["visualization"])
        self.assertEqual("count", result["definition"]["aggregation"])
        self.assertEqual("estado", result["definition"]["group_by"])
        self.assertEqual({"dashboard": False, "analytics": True}, result["placement"])

    def test_distinct_business_domains_use_their_actual_schema(self):
        prompts = [
            ("appointments", "Citas", "citas", "Crea una gráfica de citas por mes", "count"),
            ("enrollments", "Inscripciones", "matriculas", "Crea una gráfica de inscripciones por mes", "count"),
            ("trips", "Viajes", "viajes", "Crea una gráfica de viajes por mes", "count"),
            ("reservations", "Reservas", "reservas", "Crea una gráfica de reservas por mes", "count"),
            ("orders", "Órdenes", "pedidos", "Crea una gráfica de pedidos por mes", "count"),
            ("employees", "Empleados", "personal", "Crea una gráfica de empleados por mes", "count"),
        ]
        for role, name, table, phrase, metric in prompts:
            with self.subTest(role=role):
                result = self._interpret(phrase, catalog(role, name, table, include_amount=False))
                self.assertEqual(table, result["definition"]["table"])
                self.assertEqual(metric, result["definition"]["aggregation"])

    def test_unknown_field_must_not_be_invented(self):
        with self.assertRaisesRegex(ValueError, "dimensión"):
            self._interpret("Crea una gráfica de ventas por ciudad en 2026")
        with self.assertRaisesRegex(ValueError, "columna temporal"):
            self._interpret("Crea una gráfica de ventas por mes de 2026",
                            catalog(include_date=False))

    def test_financial_metric_ambiguity_requests_clarification(self):
        with self.assertRaisesRegex(ValueError, "una única métrica"):
            self._interpret("Crea una gráfica de ventas por mes",
                            catalog(multiple_amounts=True))

    def test_no_year_is_not_invented(self):
        result = self._interpret("Haz una gráfica de barras de ventas por estado")
        self.assertEqual([], result["definition"]["filters"])
        self.assertEqual("raw", result["definition"]["time_granularity"])

    def test_empty_preview_produces_editable_draft_without_fake_data(self):
        with patch.object(draft, "get_semantic_visualization_catalog",
                          return_value=catalog()):
            with patch.object(draft, "preview_visualization", return_value={
                "definition": {}, "data": [], "meta": {"rows": 0},
            }):
                with patch.object(draft.database_manager, "status",
                                  return_value={"database": "empresa", "provider": "excel"}):
                    result = draft.interpret_visualization_request(
                        "Crea gráfica de ventas por mes de 2026")
        self.assertEqual("empty", result["status"])
        self.assertEqual([], result["preview"]["data"])

    def test_chat_handler_never_calls_generic_llm_and_returns_draft(self):
        with patch.object(assistant_service, "route_request",
                          side_effect=AssertionError("LLM route must not be called")):
            with patch.object(assistant_service, "interpret_visualization_request",
                              return_value=self._interpret("Crea gráfica de ventas por mes de 2026")):
                result = assistant_service.ask_database("Crea gráfica de ventas por mes de 2026")
        self.assertEqual("visualization_draft", result["mode"])
        self.assertIsNotNone(result["visualization_draft"])
        self.assertIn("todavía", result["answer"].lower()) if result["visualization_draft"]["status"] == "empty" else self.assertIn("revisa", result["answer"].lower())

    def test_ambiguous_chat_request_asks_rather_than_persisting(self):
        with patch.object(assistant_service, "route_request",
                          side_effect=AssertionError("Route must not be called")):
            with patch.object(assistant_service, "interpret_visualization_request",
                              side_effect=ValueError("Aclara qué métrica deseas.")):
                result = assistant_service.ask_database("Haz una tabla de ventas")
        self.assertEqual("visualization_clarification", result["mode"])
        self.assertIsNone(result["visualization_draft"])
        self.assertIn("Aclara", result["answer"])


class TemporalQueryTests(unittest.TestCase):
    def setUp(self):
        self.schema = SimpleNamespace(
            database="empresa",
            tables={"ventas": SimpleNamespace(
                name="ventas", primary_key=["id"],
                columns=[
                    SimpleNamespace(name="id", type="INTEGER"),
                    SimpleNamespace(name="fecha", type="DATE"),
                    SimpleNamespace(name="total", type="DECIMAL"),
                ],
            )},
            relationships=[],
        )

    def _query(self, provider, grain):
        definition = visual.VisualizationDefinition(
            title="Ventas mensuales", visualization="bar", table="ventas",
            metric="total", aggregation="sum", group_by="fecha",
            time_granularity=grain,
        )
        with patch.object(visual, "inspect_database", return_value=self.schema):
            with patch.object(visual.database_manager, "status",
                              return_value={"provider": provider, "database": "empresa"}):
                return visual.build_visualization_query(definition)

    def test_month_grouping_is_database_specific_and_chronological(self):
        expected = {
            "excel": "strftime('%Y-%m',",
            "postgresql": "TO_CHAR(",
            "sqlserver": "CONVERT(VARCHAR(7),",
        }
        for provider, bucket in expected.items():
            with self.subTest(provider=provider):
                sql = self._query(provider, "month")
                self.assertIn(bucket, sql)
                self.assertIn("ORDER BY dimension ASC", sql)
                self.assertIn("GROUP BY ", sql)

    def test_year_grouping_is_supported(self):
        self.assertIn("'%Y'", self._query("excel", "year"))
        self.assertIn("VARCHAR(4)", self._query("sqlserver", "year"))
        self.assertIn("'YYYY'", self._query("postgresql", "year"))

    def test_sqlite_real_data_two_months_are_not_grouped_per_day(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE ventas (id INTEGER, fecha TEXT, total NUMERIC)"))
                for idx, (when, amount) in enumerate([
                    ("2026-01-05", 100), ("2026-01-15", 50),
                    ("2026-02-03", 30), ("2025-12-31", 40),
                ]):
                    conn.execute(text(
                        "INSERT INTO ventas (id, fecha, total) VALUES (:id, :when, :amount)"
                    ), {"id": idx, "when": when, "amount": amount})
            with patch.object(visual, "inspect_database", return_value=self.schema):
                with patch.object(visual.database_manager, "status",
                                  return_value={"provider": "excel"}):
                    sql = visual.build_visualization_query(visual.VisualizationDefinition(
                        title="Ventas 2026", visualization="bar", table="ventas",
                        metric="total", aggregation="sum", group_by="fecha",
                        time_granularity="month",
                        filters=[
                            visual.VisualizationFilter(column="fecha", operator="gte",
                                                       value="2026-01-01"),
                            visual.VisualizationFilter(column="fecha", operator="lt",
                                                       value="2027-01-01"),
                        ],
                    ))
                    with engine.connect() as conn:
                        rows = conn.execute(text(sql)).mappings().all()
            self.assertEqual(
                [("2026-01", 150), ("2026-02", 30)],
                [(row["dimension"], row["value"]) for row in rows],
            )
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

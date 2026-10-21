"""Builder enhancements across Kenneth's ten supported business domains."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine, text

from app.visualizations import visualization_service as engine
from app.visualizations import semantic_catalog

DOMAINS = {
    "retail": "sales",
    "education": "enrollments",
    "healthcare": "appointments",
    "transportation": "trips",
    "hospitality": "reservations",
    "restaurant": "orders",
    "professional_services": "invoices",
    "finance_accounting": "transactions",
    "manufacturing": "production_orders",
    "human_resources": "payroll",
}


def database_schema():
    return SimpleNamespace(
        database="ejemplo",
        tables={
            "registros": SimpleNamespace(
                name="registros", primary_key=["id"],
                columns=[
                    SimpleNamespace(name="id", type="INTEGER"),
                    SimpleNamespace(name="fecha", type="DATETIME"),
                    SimpleNamespace(name="importe", type="DECIMAL"),
                    SimpleNamespace(name="estado", type="VARCHAR"),
                    SimpleNamespace(name="cliente_id", type="INTEGER"),
                ],
            ),
            "personas": SimpleNamespace(
                name="personas", primary_key=["id"],
                columns=[
                    SimpleNamespace(name="id", type="INTEGER"),
                    SimpleNamespace(name="nombre", type="VARCHAR"),
                ],
            ),
        },
        relationships=[SimpleNamespace(
            table="registros", column="cliente_id",
            references_table="personas", references_column="id",
        )],
    )


class BuilderDomainEnhancementTests(unittest.TestCase):
    def test_all_supported_domains_advertise_calendar_dates_and_safe_metrics(self):
        schema = database_schema()
        for domain, role in DOMAINS.items():
            with self.subTest(domain=domain):
                response = {"semantic_model": {
                    "domain": domain,
                    "entities": {role: {
                        "table": "registros",
                        "columns": {"date": "fecha", "total": "importe", "status": "estado"},
                    }},
                }}
                with patch.object(semantic_catalog, "inspect_database", return_value=schema):
                    with patch.object(semantic_catalog, "inspect_semantic_model",
                                      return_value=response):
                        catalog = semantic_catalog.get_semantic_visualization_catalog()
                entity = next(item for item in catalog["entities"]
                              if item["table"] == "registros")
                self.assertEqual(role, entity["semantic_role"])
                date = next(item for item in entity["fields"] if item["key"] == "fecha")
                self.assertEqual("date", date["kind"])
                self.assertEqual("date", date["semantic"])
                amount = next(item for item in entity["metrics"]
                              if item["key"] == "importe")
                self.assertIn("sum", amount["aggregations"])
                self.assertIn("avg", amount["aggregations"])

    def test_calendar_day_bucketing_excludes_time_of_day(self):
        schema = database_schema()
        engine_instance = create_engine("sqlite+pysqlite:///:memory:")
        try:
            with engine_instance.begin() as conn:
                conn.execute(text(
                    "CREATE TABLE registros(id INTEGER,fecha TEXT,importe NUMERIC,"
                    " estado TEXT,cliente_id INTEGER)"
                ))
                for number, stamp, amount in [
                    (1, "2026-01-01 09:00:00", 20),
                    (2, "2026-01-01 17:00:00", 30),
                    (3, "2026-01-02 09:00:00", 40),
                ]:
                    conn.execute(text(
                        "INSERT INTO registros(id,fecha,importe) VALUES(:id,:d,:amount)"
                    ), {"id": number, "d": stamp, "amount": amount})
            definition = engine.VisualizationDefinition(
                title="Actividad diaria", visualization="area", table="registros",
                metric="importe", aggregation="sum", group_by="fecha",
                time_granularity="day", limit=100,
            )
            with patch.object(engine, "inspect_database", return_value=schema):
                with patch.object(engine.database_manager, "status",
                                  return_value={"provider": "excel"}):
                    sql = engine.build_visualization_query(definition)
            with engine_instance.connect() as conn:
                result = list(conn.execute(text(sql)).mappings())
            self.assertEqual(
                [("2026-01-01", 50), ("2026-01-02", 40)],
                [(row["dimension"], int(row["value"])) for row in result],
            )
        finally:
            engine_instance.dispose()

    def test_calendar_day_generation_is_dialect_aware(self):
        definition = engine.VisualizationDefinition(
            title="Actividad diaria", visualization="line", table="registros",
            group_by="fecha", time_granularity="day",
        )
        for provider, expected in [
            ("excel", "strftime('%Y-%m-%d'"),
            ("sqlserver", "CONVERT(VARCHAR(10),"),
            ("postgresql", "TO_CHAR("),
        ]:
            with self.subTest(provider=provider):
                with patch.object(engine, "inspect_database",
                                  return_value=database_schema()):
                    with patch.object(engine.database_manager, "status",
                                      return_value={"provider": provider}):
                        query = engine.build_visualization_query(definition)
                self.assertIn(expected, query)
                self.assertIn("ORDER BY dimension ASC", query)

    def test_related_parent_amount_must_not_duplicate_fact_revenue(self):
        definition = engine.VisualizationDefinition(
            title="Prohibir suma vinculada", visualization="bar",
            table="registros", metric="id", metric_table="personas",
            aggregation="sum", group_by="estado",
        )
        with patch.object(engine, "inspect_database", return_value=database_schema()):
            with self.assertRaisesRegex(ValueError, "duplicar"):
                engine.build_visualization_query(definition)

    def test_unverified_dimensions_and_bad_date_granularity_fail(self):
        with self.assertRaises(ValidationError):
            engine.VisualizationDefinition(
                title="Trimestre sin fecha", visualization="bar",
                table="registros", time_granularity="quarter",
            )
        definition = engine.VisualizationDefinition(
            title="Fechas falsas", visualization="bar", table="registros",
            group_by="estado", time_granularity="day",
        )
        with patch.object(engine, "inspect_database", return_value=database_schema()):
            with self.assertRaisesRegex(ValueError, "columna de fecha"):
                engine.build_visualization_query(definition)

    def test_nullable_filters_and_two_bound_dates_are_supported(self):
        definitions = [
            engine.VisualizationDefinition(
                title="Sin estado", visualization="bar", table="registros",
                group_by="estado",
                filters=[engine.VisualizationFilter(
                    column="estado", operator="is_null", value="",
                )],
            ),
            engine.VisualizationDefinition(
                title="Fechas acotadas", visualization="line", table="registros",
                group_by="fecha", time_granularity="day",
                filters=[engine.VisualizationFilter(
                    column="fecha", operator="between",
                    value=["2026-01-01", "2026-12-31"],
                )],
            ),
        ]
        with patch.object(engine, "inspect_database", return_value=database_schema()):
            with patch.object(engine.database_manager, "status",
                              return_value={"provider": "excel"}):
                sql = [engine.build_visualization_query(item) for item in definitions]
        self.assertIn("IS NULL", sql[0])
        self.assertIn("BETWEEN", sql[1])
        self.assertIn("'2026-01-01'", sql[1])
        self.assertIn("'2026-12-31'", sql[1])


if __name__ == "__main__":
    unittest.main()

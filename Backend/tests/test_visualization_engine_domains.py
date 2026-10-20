"""Cross-domain visualization engine validation for Kenneth.

SQLite checks actual amounts and joins. Mocked dialects check SQL generation
for PostgreSQL and SQL Server. No user or production business records are used.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine, text

from app.visualizations import semantic_catalog as catalog_service
from app.visualizations import visualization_service as engine

BUSINESS_DOMAINS = {
    "retail": "sales", "education": "enrollments",
    "healthcare": "appointments", "transportation": "trips",
    "hospitality": "reservations", "restaurant": "orders",
    "professional_services": "invoices", "finance_accounting": "transactions",
    "manufacturing": "production_orders", "human_resources": "payroll",
}


def schema():
    return SimpleNamespace(
        database="empresa_demo",
        tables={
            "facts": SimpleNamespace(
                name="facts", primary_key=["id"],
                columns=[
                    SimpleNamespace(name="id", type="INTEGER"),
                    SimpleNamespace(name="fecha", type="DATE"),
                    SimpleNamespace(name="total", type="DECIMAL"),
                    SimpleNamespace(name="estado", type="VARCHAR"),
                    SimpleNamespace(name="owner_id", type="INTEGER"),
                ],
            ),
            "owners": SimpleNamespace(
                name="owners", primary_key=["id"],
                columns=[
                    SimpleNamespace(name="id", type="INTEGER"),
                    SimpleNamespace(name="nombre", type="VARCHAR"),
                    SimpleNamespace(name="region", type="VARCHAR"),
                    SimpleNamespace(name="minimo", type="INTEGER"),
                ],
            ),
            "lines": SimpleNamespace(
                name="lines", primary_key=["id"],
                columns=[
                    SimpleNamespace(name="id", type="INTEGER"),
                    SimpleNamespace(name="fact_id", type="INTEGER"),
                    SimpleNamespace(name="cantidad", type="INTEGER"),
                ],
            ),
        },
        relationships=[
            SimpleNamespace(
                table="facts", column="owner_id",
                references_table="owners", references_column="id",
            ),
            SimpleNamespace(
                table="lines", column="fact_id",
                references_table="facts", references_column="id",
            ),
        ],
    )


def create_data():
    sql_engine = create_engine("sqlite+pysqlite:///:memory:")
    with sql_engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE owners(id INTEGER PRIMARY KEY, nombre TEXT, "
            "region TEXT, minimo INT)"
        ))
        conn.execute(text(
            "CREATE TABLE facts(id INTEGER PRIMARY KEY, fecha TEXT, "
            "total NUMERIC, estado TEXT, owner_id INT)"
        ))
        conn.execute(text(
            "CREATE TABLE lines(id INTEGER PRIMARY KEY, fact_id INT, cantidad INT)"
        ))
        for row in [(1, "Ana", "Este", 10), (2, "Beto", "Oeste", 5),
                    (3, "Ana", "Oeste", 3)]:
            conn.execute(text(
                "INSERT INTO owners VALUES (:id,:name,:region,:min)"
            ), dict(zip(("id", "name", "region", "min"), row)))
        for row in [
            (1, "2025-01-05", 100, "ok", 1),
            (2, "2025-01-21", 25, "ok", 1),
            (3, "2025-04-02", 40, "pending", 2),
            (4, "2025-07-11", 20, "ok", 3),
            (5, "2025-11-08", None, "cancelled", 3),
        ]:
            conn.execute(text(
                "INSERT INTO facts VALUES (:id,:fecha,:total,:estado,:owner_id)"
            ), dict(zip(("id", "fecha", "total", "estado", "owner_id"), row)))
        for row in [(1,1,1), (2,1,3), (3,2,1), (4,3,4)]:
            conn.execute(text(
                "INSERT INTO lines VALUES (:id,:fact_id,:quantity)"
            ), dict(zip(("id", "fact_id", "quantity"), row)))
    return sql_engine


class EngineDomainCases(unittest.TestCase):
    def setUp(self):
        self.layout = schema()
        self.database = create_data()

    def tearDown(self):
        self.database.dispose()

    def run_query(self, definition):
        with patch.object(engine, "inspect_database", return_value=self.layout):
            with patch.object(engine.database_manager, "status", return_value={
                "database": "empresa_demo", "provider": "excel",
            }):
                sql = engine.build_visualization_query(definition)
        with self.database.connect() as conn:
            return sql, [dict(r) for r in conn.execute(text(sql)).mappings().all()]

    def test_all_ten_domains_have_schema_grounded_numeric_and_unique_metrics(self):
        for domain, role in BUSINESS_DOMAINS.items():
            with self.subTest(domain=domain, role=role):
                semantic = {"semantic_model": {
                    "domain": domain,
                    "entities": {role: {
                        "table": "facts", "confidence": "high",
                        "columns": {
                            "id": "id", "date": "fecha",
                            "total": "total", "status": "estado",
                        },
                    }},
                }}
                with patch.object(catalog_service, "inspect_database", return_value=self.layout):
                    with patch.object(catalog_service, "inspect_semantic_model",
                                      return_value=semantic):
                        result = catalog_service.get_semantic_visualization_catalog()
                selected = next(e for e in result["entities"] if e["table"] == "facts")
                self.assertEqual(role, selected["semantic_role"])
                self.assertIn("total", {field["key"] for field in selected["metrics"]})
                self.assertIn("fecha", {field["key"] for field in selected["dimensions"]})
                self.assertIn("distinct_count", {
                    choice for item in selected["metrics"] for choice in item["aggregations"]
                })
                self.assertEqual(["id"], selected["primary_key"])

    def test_facts_sum_does_not_duplicate_after_related_grouping(self):
        definition = engine.VisualizationDefinition(
            title="Cifras por región", visualization="bar", table="facts",
            metric="total", aggregation="sum",
            group_by="region", group_by_table="owners",
        )
        query, rows = self.run_query(definition)
        self.assertIn('JOIN "owners"', query)
        self.assertEqual([("Este", 125), ("Oeste", 60)],
                         sorted((r["dimension"], int(r["value"])) for r in rows))

    def test_reverse_join_would_multiply_metrics_and_is_rejected(self):
        definition = engine.VisualizationDefinition(
            title="Importes de propietarios", visualization="bar",
            table="owners", metric="minimo", aggregation="sum",
            group_by="estado", group_by_table="facts",
        )
        with self.assertRaisesRegex(ValueError, "muchos-a-uno"):
            self.run_query(definition)

    def test_ambiguous_two_foreign_keys_to_same_parent_refused(self):
        complicated = schema()
        complicated.relationships.append(SimpleNamespace(
            table="facts", column="owner_id",
            references_table="owners", references_column="id",
        ))
        definition = engine.VisualizationDefinition(
            title="Owners", visualization="bar", table="facts",
            group_by="nombre", group_by_table="owners",
        )
        with patch.object(engine, "inspect_database", return_value=complicated):
            with self.assertRaisesRegex(ValueError, "varias rutas"):
                engine.build_visualization_query(definition)

    def test_invalid_sums_of_joined_parent_metrics_are_blocked(self):
        definition = engine.VisualizationDefinition(
            title="Mínimo multiplicado", visualization="bar",
            table="facts", metric="minimo", metric_table="owners",
            aggregation="sum", group_by="estado",
        )
        with self.assertRaisesRegex(ValueError, "duplicar"):
            self.run_query(definition)

    def test_distinct_count_handles_several_transactions_per_person(self):
        definition = engine.VisualizationDefinition(
            title="Propietarios únicos", visualization="kpi", table="facts",
            metric="owner_id", aggregation="distinct_count",
        )
        _, rows = self.run_query(definition)
        self.assertEqual(3, rows[0]["value"])
        with self.assertRaises(ValidationError):
            engine.VisualizationDefinition(
                title="Incompleto", visualization="kpi", table="facts",
                aggregation="distinct_count",
            )

    def test_quarterly_aggregation_has_calendar_correctness(self):
        definition = engine.VisualizationDefinition(
            title="Cifras trimestrales", visualization="area",
            table="facts", metric="total", aggregation="sum",
            group_by="fecha", time_granularity="quarter",
        )
        _, rows = self.run_query(definition)
        self.assertEqual([
            ("2025-Q1", 125), ("2025-Q2", 40), ("2025-Q3", 20),
        ], [(r["dimension"], int(r["value"])) for r in rows if r["value"] is not None])
        for dialect, expected in [
            ("sqlserver", "DATEPART(QUARTER"),
            ("postgresql", "EXTRACT(QUARTER"),
        ]:
            with patch.object(engine, "inspect_database", return_value=self.layout):
                with patch.object(engine.database_manager, "status",
                                  return_value={"provider": dialect}):
                    self.assertIn(expected, engine.build_visualization_query(definition))

    def test_null_between_and_multi_column_detail_table(self):
        definition = engine.VisualizationDefinition(
            title="Revisión de actividad", visualization="table", table="facts",
            table_mode="detail",
            detail_columns=[
                engine.VisualizationColumn(column="fecha"),
                engine.VisualizationColumn(column="estado"),
                engine.VisualizationColumn(table="owners", column="region"),
                engine.VisualizationColumn(column="total"),
            ],
            filters=[
                engine.VisualizationFilter(column="total", operator="not_null", value=""),
                engine.VisualizationFilter(column="total", operator="between", value=[20, 100]),
            ],
            limit=100, sort_direction="asc",
        )
        query, rows = self.run_query(definition)
        self.assertIn("ORDER BY field_0 ASC", query)
        self.assertEqual(["field_0", "field_1", "field_2", "field_3"], list(rows[0]))
        self.assertEqual(4, len(rows))
        self.assertTrue(all("field_2" in row for row in rows))

    def test_detail_table_must_have_valid_selected_columns(self):
        with self.assertRaises(ValidationError):
            engine.VisualizationDefinition(
                title="Sin columnas", visualization="table",
                table="facts", table_mode="detail",
            )
        with self.assertRaises(ValidationError):
            engine.VisualizationDefinition(
                title="Demasiadas", visualization="table", table="facts",
                table_mode="detail",
                detail_columns=[{"column": "total"} for _ in range(9)],
            )
        incorrect = engine.VisualizationDefinition(
            title="Datos", visualization="table", table="facts",
            table_mode="detail",
            detail_columns=[{"table": "facts", "column": "inexistente"}],
        )
        with self.assertRaisesRegex(ValueError, "no existe"):
            self.run_query(incorrect)

    def test_group_by_pk_preserves_distinct_name_entities(self):
        definition = engine.VisualizationDefinition(
            title="Por propietario", visualization="bar", table="facts",
            group_by="nombre", group_by_table="owners",
            group_by_identity="id",
        )
        _, rows = self.run_query(definition)
        self.assertEqual(3, len(rows))
        self.assertEqual({("Ana (#1)", 2), ("Beto (#2)", 1), ("Ana (#3)", 2)},
                         {(r["dimension"], r["value"]) for r in rows})

    def test_legacy_saved_definitions_continue_to_parse(self):
        for vis in ("bar", "line", "donut", "table", "kpi"):
            with self.subTest(vis=vis):
                result = engine.VisualizationDefinition.model_validate({
                    "title": "Legacy", "table": "facts", "visualization": vis,
                    "aggregation": "count",
                    **({"group_by": "estado"} if vis in {"bar","line","donut"} else {}),
                })
                self.assertEqual("aggregate", result.table_mode)
                self.assertEqual("raw", result.time_granularity)


if __name__ == "__main__":
    unittest.main()

"""Tests for cross-table minimum policies used by critical inventory previews."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, text

from app.visualizations import conversational_drafts as drafts
from app.visualizations import visualization_service as visual


def source():
    inventory = {
        "key": "inventory", "semantic_role": "inventory",
        "label": "Inventario", "table": "inventario",
        "fields": [{
            "key": "stock", "label": "Existencias", "semantic": "stock",
            "kind": "number", "metric": True, "filter": True,
            "aggregations": ["sum"],
        }],
        "metrics": [], "filters": [], "dimensions": [],
    }
    products = {
        "key": "products", "semantic_role": "products",
        "label": "Productos", "table": "productos",
        "fields": [
            {"key": "nombre", "label": "Nombre", "semantic": "name", "kind": "text",
             "dimension": True},
            {"key": "minimo", "label": "Mínimo", "semantic": "minimum", "kind": "number"},
        ],
        "metrics": [], "filters": [],
        "dimensions": [{
            "key": "nombre", "label": "Nombre", "semantic": "name",
            "kind": "text", "dimension": True,
        }],
    }
    return {
        "entities": [inventory, products],
        "relationships": [{
            "from_table": "inventario", "from_column": "producto_id",
            "to_table": "productos", "to_column": "id",
        }],
    }


def schema():
    return SimpleNamespace(
        database="empresa",
        tables={
            "inventario": SimpleNamespace(
                primary_key=["id"],
                columns=[SimpleNamespace(name=k, type="INTEGER")
                         for k in ("id", "producto_id", "stock")],
            ),
            "productos": SimpleNamespace(
                primary_key=["id"],
                columns=[
                    SimpleNamespace(name="id", type="INTEGER"),
                    SimpleNamespace(name="nombre", type="VARCHAR"),
                    SimpleNamespace(name="minimo", type="INTEGER"),
                ],
            ),
        },
        relationships=[SimpleNamespace(
            table="inventario", column="producto_id",
            references_table="productos", references_column="id",
        )],
    )


class CriticalInventoryRelatedMinimumTests(unittest.TestCase):
    def test_related_product_minimum_is_used_with_read_only_preview(self):
        with patch.object(drafts, "get_semantic_visualization_catalog",
                          return_value=source()):
            with patch("app.database.inspector.inspect_database", return_value=schema()):
                with patch("app.database.query_executor.execute_query", return_value=[]):
                    with patch.object(drafts.database_manager, "status",
                                      return_value={"provider": "excel", "database": "empresa"}):
                        with patch.object(drafts, "preview_visualization",
                                          return_value={"data": [], "meta": {"rows": 0}}):
                            result = drafts.interpret_visualization_request(
                                "hazme una grafica con los productos en inventario critico"
                            )
        condition = result["definition"]["filters"][0]
        self.assertEqual("lte_field", condition["operator"])
        self.assertEqual("inventario", condition["table"])
        self.assertEqual("productos", condition["value_table"])
        self.assertEqual("minimo", condition["value"])
        self.assertEqual("empty", result["status"])
        self.assertEqual("productos", result["definition"]["group_by_table"])

    def test_filtered_sql_uses_product_minimum_not_fake_numeric_threshold(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    "CREATE TABLE productos(id INTEGER PRIMARY KEY,nombre TEXT,minimo INTEGER)"
                ))
                conn.execute(text(
                    "CREATE TABLE inventario(id INTEGER PRIMARY KEY,producto_id INTEGER,stock INTEGER)"
                ))
                for pk, name, minimum, stock in (
                    (1, "Teclado", 5, 3),
                    (2, "Mouse", 5, 18),
                    (3, "Monitor", 0, 0),
                ):
                    conn.execute(text(
                        "INSERT INTO productos(id,nombre,minimo) VALUES (:pk,:name,:min)"
                    ), {"pk": pk, "name": name, "min": minimum})
                    conn.execute(text(
                        "INSERT INTO inventario(id,producto_id,stock) VALUES (:pk,:pk,:stock)"
                    ), {"pk": pk, "stock": stock})
            definition = visual.VisualizationDefinition(
                title="Stock crítico", visualization="bar",
                table="inventario", metric="stock", aggregation="sum",
                group_by="nombre", group_by_table="productos",
                group_by_identity="id", sort_direction="asc", limit=50,
                filters=[visual.VisualizationFilter(
                    table="inventario", column="stock", operator="lte_field",
                    value_table="productos", value="minimo",
                )],
            )
            with patch.object(visual, "inspect_database", return_value=schema()):
                with patch.object(visual.database_manager, "status",
                                  return_value={"provider": "excel"}):
                    sql = visual.build_visualization_query(definition)
            self.assertIn('"inventario"."stock" <= "productos"."minimo"', sql)
            with engine.connect() as conn:
                rows = list(conn.execute(text(sql)).mappings().all())
            self.assertEqual([0, 3], [int(row["value"]) for row in rows])
        finally:
            engine.dispose()

    def test_reverse_or_unrelated_column_comparison_fails(self):
        definition = visual.VisualizationDefinition(
            title="Unsafe comparison", visualization="bar", table="productos",
            metric="id", aggregation="sum", group_by="nombre",
            filters=[visual.VisualizationFilter(
                table="productos", column="id",
                operator="lte_field", value_table="inventario", value="stock",
            )],
        )
        with patch.object(visual, "inspect_database", return_value=schema()):
            with self.assertRaisesRegex(ValueError, "relación única"):
                visual.build_visualization_query(definition)


if __name__ == "__main__":
    unittest.main()

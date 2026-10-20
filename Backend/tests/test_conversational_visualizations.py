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


def customer_ranking_catalog():
    customer = {
        "key": "customers", "semantic_role": "customers",
        "label": "Clientes", "table": "clientes",
        "fields": [
            {"key": "id", "label": "ID", "semantic": "id",
             "kind": "number", "dimension": False},
            {"key": "nombre", "label": "Nombre", "semantic": "name",
             "kind": "text", "dimension": True},
        ],
        "dimensions": [{"key": "nombre", "label": "Nombre", "semantic": "name",
                        "kind": "text", "dimension": True}],
        "metrics": [],
    }
    sales = {
        "key": "sales", "semantic_role": "sales", "label": "Ventas", "table": "ventas",
        "fields": [
            {"key": "fecha", "label": "Fecha", "semantic": "date", "kind": "date"},
            {"key": "total", "label": "Total", "semantic": "total",
             "kind": "number", "aggregations": ["sum", "avg", "count"]},
        ],
        "metrics": [
            {"key": "total", "label": "Total", "semantic": "total",
             "kind": "number", "aggregations": ["sum", "avg", "count"]},
        ],
        "dimensions": [
            {"key": "fecha", "label": "Fecha", "semantic": "date", "kind": "date"},
        ],
    }
    return {
        "entities": [sales, customer],
        "relationships": [{
            "from_table": "ventas", "from_column": "cliente_id",
            "to_table": "clientes", "to_column": "id",
        }],
    }


def customer_schema():
    return SimpleNamespace(
        database="empresa",
        tables={
            "ventas": SimpleNamespace(
                name="ventas", primary_key=["id"],
                columns=[
                    SimpleNamespace(name="id", type="INTEGER"),
                    SimpleNamespace(name="cliente_id", type="INTEGER"),
                    SimpleNamespace(name="fecha", type="DATE"),
                    SimpleNamespace(name="total", type="NUMERIC"),
                ],
            ),
            "clientes": SimpleNamespace(
                name="clientes", primary_key=["id"],
                columns=[
                    SimpleNamespace(name="id", type="INTEGER"),
                    SimpleNamespace(name="nombre", type="VARCHAR"),
                ],
            ),
        },
        relationships=[
            SimpleNamespace(
                table="ventas", column="cliente_id",
                references_table="clientes", references_column="id",
            ),
        ],
    )


class CustomerRankingFollowupTests(unittest.TestCase):
    REQUEST = "Puedes crearme una grafica que tenga los 5 clientes que compran menos?"

    def _generate(self, question, semantic=None):
        semantic = semantic or customer_ranking_catalog()
        schema = customer_schema()
        with patch.object(draft, "get_semantic_visualization_catalog",
                          return_value=semantic):
            with patch("app.database.inspector.inspect_database", return_value=schema):
                with patch.object(draft, "preview_visualization",
                                  side_effect=fake_preview):
                    with patch.object(draft.database_manager, "status",
                                      return_value={"provider": "excel",
                                                    "database": "empresa"}):
                        return draft.interpret_visualization_request(question)

    def test_user_question_is_valid_but_metric_is_ambiguous(self):
        self.assertTrue(draft.is_visualization_creation_request(self.REQUEST))
        with self.assertRaisesRegex(ValueError, "importe gastado.*número"):
            self._generate(self.REQUEST)

    def test_bottom_five_sales_amount_has_join_ascending_and_identity(self):
        result = self._generate(self.REQUEST + " por importe")
        definition = result["definition"]
        self.assertEqual("ventas", definition["table"])
        self.assertEqual("clientes", definition["group_by_table"])
        self.assertEqual("nombre", definition["group_by"])
        self.assertEqual("id", definition["group_by_identity"])
        self.assertEqual("total", definition["metric"])
        self.assertEqual("sum", definition["aggregation"])
        self.assertEqual("asc", definition["sort_direction"])
        self.assertEqual(5, definition["limit"])
        self.assertEqual("Clientes", result["axes"]["x"])

    def test_bottom_five_frequency_is_count_without_money(self):
        result = self._generate(
            "Crea una grafica de los 5 clientes con menos compras"
        )
        self.assertEqual("count", result["definition"]["aggregation"])
        self.assertIsNone(result["definition"]["metric"])
        self.assertEqual(5, result["definition"]["limit"])

    def test_no_join_refuses_to_guess_customer_relationship(self):
        schema = customer_ranking_catalog()
        schema["relationships"] = []
        with self.assertRaisesRegex(ValueError, "relación inequívoca"):
            self._generate(self.REQUEST + " por importe", schema)

    def test_chat_followup_preserves_customer_ranking_request(self):
        # Exercise real request parser but avoid DB calls until metric is known.
        with patch.object(draft, "get_semantic_visualization_catalog",
                          return_value=customer_ranking_catalog()):
            first = assistant_service.ask_database(self.REQUEST)
        self.assertEqual("visualization_clarification", first["mode"])
        self.assertIn("importe", first["answer"])
        history = [
            {"role": "user", "content": self.REQUEST},
            {"role": "assistant", "content": first["answer"]},
        ]
        # Relevant answer completes the draft; no second SQL-chat route.
        result = self._generate(self.REQUEST + " por cantidad de compras")
        with patch.object(assistant_service, "interpret_visualization_request",
                          return_value=result) as mocked:
            with patch.object(assistant_service, "route_request",
                              side_effect=AssertionError("generic route called")):
                second = assistant_service.ask_database("por cantidad de compras",
                                                        history=history)
            mocked.assert_called_once_with(self.REQUEST + " por cantidad de compras")
        self.assertEqual("visualization_draft", second["mode"])
        self.assertEqual("asc", second["visualization_draft"]["definition"]["sort_direction"])

        # Irrelevant follow-up must stay in ranking clarification, not switch to
        # an independent category ranking.
        with patch.object(draft, "get_semantic_visualization_catalog",
                          return_value=customer_ranking_catalog()):
            with patch.object(assistant_service, "route_request",
                              side_effect=AssertionError("generic route called")):
                third = assistant_service.ask_database("por categoria", history=history)
        self.assertEqual("visualization_clarification", third["mode"])
        self.assertIn("ranking de clientes", third["answer"])
        self.assertIsNone(third["visualization_draft"])

    def test_real_sqlite_ranking_keeps_same_names_separate_and_ascending(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        schema = customer_schema()
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE clientes (id INT PRIMARY KEY, nombre TEXT)"))
                conn.execute(text(
                    "CREATE TABLE ventas (id INT PRIMARY KEY, cliente_id INT,"
                    " fecha TEXT, total NUMERIC)"
                ))
                for client, name in [(1, "Ana"), (2, "Ana"), (3, "Carlos"),
                                     (4, "Diego"), (5, "Eva"), (6, "Francisca")]:
                    conn.execute(text(
                        "INSERT INTO clientes(id, nombre) VALUES (:id, :name)"
                    ), {"id": client, "name": name})
                for index, client, value in [(1,1,200),(2,2,10),(3,2,5),
                                             (4,3,30),(5,4,50),(6,5,80),(7,6,100)]:
                    conn.execute(text(
                        "INSERT INTO ventas(id, cliente_id, fecha, total)"
                        " VALUES (:id, :client, '2026-01-10', :value)"
                    ), {"id": index, "client": client, "value": value})
            req = visual.VisualizationDefinition(
                title="5 clientes que compraron menos", visualization="bar",
                table="ventas", metric="total", metric_table="ventas",
                aggregation="sum", group_by="nombre",
                group_by_table="clientes", group_by_identity="id",
                sort_direction="asc", limit=5,
            )
            with patch.object(visual, "inspect_database", return_value=schema):
                with patch.object(visual.database_manager, "status",
                                  return_value={"provider":"excel","database":"empresa"}):
                    sql = visual.build_visualization_query(req)
            self.assertIn("ORDER BY value ASC", sql)
            with engine.connect() as conn:
                rows = conn.execute(text(sql)).mappings().all()
            self.assertEqual(5, len(rows))
            self.assertEqual([15, 30, 50, 80, 100],
                             [int(row["value"]) for row in rows])
            self.assertEqual("Ana (#2)", rows[0]["dimension"])
            self.assertNotIn("Ana (#1)", [row["dimension"] for row in rows])
            # Count number of purchases gives 1, 2 etc without aggregating
            # different clients with identical display names.
            count_req = req.model_copy(update={"metric": None, "aggregation": "count"})
            with patch.object(visual, "inspect_database", return_value=schema):
                with patch.object(visual.database_manager, "status",
                                  return_value={"provider":"excel","database":"empresa"}):
                    count_sql = visual.build_visualization_query(count_req)
            with engine.connect() as conn:
                count_rows = conn.execute(text(count_sql)).mappings().all()
            self.assertEqual(5, len(count_rows))
            self.assertEqual(1, min(row["value"] for row in count_rows))
        finally:
            engine.dispose()



def inventory_catalog(*, embedded_name=False, include_minimum=True, role_on_products=False):
    owner_role = "products" if role_on_products else "inventory"
    stock_fields = [
        {"key": "stock", "label": "Existencias", "semantic": "stock",
         "kind": "number", "is_identifier": False, "metric": True, "filter": True,
         "aggregations": ["sum", "avg", "count"]},
    ]
    if include_minimum:
        stock_fields.append({
            "key": "stock_minimo", "label": "Stock mínimo",
            "semantic": "minimum", "kind": "number", "is_identifier": False,
            "metric": True, "filter": True, "aggregations": ["sum", "avg", "count"],
        })
    if embedded_name:
        stock_fields.append({
            "key": "nombre_producto", "label": "Nombre producto", "semantic": "name",
            "kind": "text", "dimension": True, "filter": True,
        })
    owner = {
        "key": owner_role, "semantic_role": owner_role,
        "label": "Productos" if role_on_products else "Inventario",
        "table": "productos" if role_on_products else "inventario",
        "fields": stock_fields,
        "metrics": [item for item in stock_fields if item.get("metric")],
        "dimensions": [item for item in stock_fields if item.get("dimension")],
        "filters": [item for item in stock_fields if item.get("filter")],
    }
    if role_on_products:
        owner["fields"].append({
            "key": "nombre", "label": "Nombre", "semantic": "name",
            "kind": "text", "dimension": True, "filter": True,
        })
        owner["dimensions"] = [owner["fields"][-1]]
        return {"entities": [owner], "relationships": []}
    products = {
        "key": "products", "semantic_role": "products", "label": "Productos",
        "table": "productos", "fields": [
            {"key": "nombre", "label": "Nombre", "semantic": "name",
             "kind": "text", "dimension": True, "filter": True},
        ],
        "metrics": [], "filters": [],
        "dimensions": [
            {"key": "nombre", "label": "Nombre", "semantic": "name",
             "kind": "text", "dimension": True},
        ],
    }
    return {"entities": [owner, products], "relationships": [{
        "from_table": "inventario", "from_column": "producto_id",
        "to_table": "productos", "to_column": "id",
    }]}


def inventory_schema(*, embedded_name=False, product_stock=False):
    fields = [
        SimpleNamespace(name="id", type="INTEGER"),
        SimpleNamespace(name="stock", type="INTEGER"),
        SimpleNamespace(name="stock_minimo", type="INTEGER"),
    ]
    if embedded_name:
        fields.append(SimpleNamespace(name="nombre_producto", type="VARCHAR"))
    if not product_stock:
        fields.append(SimpleNamespace(name="producto_id", type="INTEGER"))
    products = [
        SimpleNamespace(name="id", type="INTEGER"),
        SimpleNamespace(name="nombre", type="VARCHAR"),
    ]
    return SimpleNamespace(
        database="empresa",
        tables={
            "inventario": SimpleNamespace(
                name="inventario", columns=fields,
                primary_key=["id"],
            ),
            "productos": SimpleNamespace(
                name="productos", columns=fields if product_stock else products,
                primary_key=["id"],
            ),
        },
        relationships=[
            SimpleNamespace(
                table="inventario", column="producto_id",
                references_table="productos", references_column="id",
            ),
        ] if not product_stock else [],
    )


class CriticalInventoryTests(unittest.TestCase):
    REQUEST = "hazme una grafica con los productos en inventario critico"

    def _proposal(self, question=None, catalog_data=None, schema=None,
                  duplicates=None):
        with patch.object(draft, "get_semantic_visualization_catalog",
                          return_value=catalog_data or inventory_catalog()):
            with patch("app.database.inspector.inspect_database",
                       return_value=schema or inventory_schema()):
                with patch("app.database.query_executor.execute_query",
                           return_value=duplicates or []):
                    with patch.object(draft.database_manager, "status",
                                      return_value={"provider": "excel", "database": "empresa"}):
                        with patch.object(draft, "preview_visualization",
                                          side_effect=fake_preview):
                            return draft.interpret_visualization_request(question or self.REQUEST)

    def test_inventory_products_are_related_not_competing_entities(self):
        proposal = self._proposal()
        config = proposal["definition"]
        self.assertEqual("inventario", config["table"])
        self.assertEqual("productos", config["group_by_table"])
        self.assertEqual("nombre", config["group_by"])
        self.assertEqual("stock", config["metric"])
        self.assertEqual("sum", config["aggregation"])
        self.assertEqual("id", config["group_by_identity"])
        self.assertEqual("asc", config["sort_direction"])
        self.assertEqual([{
            "table": "inventario", "column": "stock", "operator": "lte_field",
            "value": "stock_minimo",
        }], config["filters"])
        self.assertIn("menor o igual", proposal["notes"][1])

    def test_followup_inventory_does_not_repeat_entity_conflict(self):
        question = self.REQUEST + " seria el inventario"
        proposal = self._proposal(question)
        self.assertEqual("ready", proposal["status"])
        self.assertEqual("inventario", proposal["definition"]["table"])
        with patch.object(assistant_service, "interpret_visualization_request",
                          return_value=proposal) as called:
            with patch.object(assistant_service, "route_request",
                              side_effect=AssertionError("restarted generic conversation")):
                answer = assistant_service.ask_database(
                    "sería el inventario", history=[
                        {"role": "user", "content": self.REQUEST},
                        {"role": "assistant", "content":
                         "Para continuar con la visualización: "
                         "La solicitud coincide con varias entidades: Inventario, Productos. "
                         "Especifica cuál deseas analizar."},
                    ],
                )
        called.assert_called_once_with(self.REQUEST + " sería el inventario")
        self.assertEqual("visualization_draft", answer["mode"])

    def test_product_schema_can_contain_stock_and_minimum_directly(self):
        proposal = self._proposal(
            catalog_data=inventory_catalog(role_on_products=True),
            schema=inventory_schema(product_stock=True),
        )
        self.assertEqual("productos", proposal["definition"]["table"])
        self.assertEqual("productos", proposal["definition"]["group_by_table"])

    def test_missing_minimum_is_reported_not_faked(self):
        with self.assertRaisesRegex(ValueError, "mínimo permitido"):
            self._proposal(catalog_data=inventory_catalog(include_minimum=False))

    def test_multiple_warehouse_stock_rows_not_called_total_product_shortage(self):
        with self.assertRaisesRegex(ValueError, "varios registros"):
            self._proposal(duplicates=[{"product_id": 123}])

    def test_unlinked_inventory_not_used_to_guess_product_names(self):
        data = inventory_catalog()
        data["relationships"] = []
        with self.assertRaisesRegex(ValueError, "nombre de producto"):
            self._proposal(catalog_data=data)

    def test_filter_rejects_non_numeric_comparison_and_injection(self):
        schema = inventory_schema()
        req = visual.VisualizationDefinition(
            title="Critical inventory", visualization="bar", table="inventario",
            metric="stock", aggregation="sum", group_by="id",
            filters=[
                visual.VisualizationFilter(
                    table="inventario", column="stock",
                    operator="lte_field", value="stock_minimo; DROP TABLE inventario",
                ),
            ],
        )
        with patch.object(visual, "inspect_database", return_value=schema):
            with self.assertRaisesRegex(ValueError, "no existe"):
                visual.build_visualization_query(req)

    def test_sqlite_real_data_only_critical_rows_are_included(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        schema = inventory_schema()
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    "CREATE TABLE productos (id INTEGER PRIMARY KEY, nombre TEXT)"
                ))
                conn.execute(text(
                    "CREATE TABLE inventario (id INTEGER PRIMARY KEY, producto_id INTEGER,"
                    " stock INTEGER, stock_minimo INTEGER)"
                ))
                for pk, name in [(1, "Teclado"), (2, "Mouse"), (3, "Monitor"), (4, "Monitor")]:
                    conn.execute(text(
                        "INSERT INTO productos(id,nombre) VALUES (:pk,:name)"
                    ), {"pk": pk, "name": name})
                for pk, item, stock, minimum in [
                    (1,1,3,5), (2,2,20,5), (3,3,0,1), (4,4,8,8),
                ]:
                    conn.execute(text(
                        "INSERT INTO inventario(id,producto_id,stock,stock_minimo)"
                        " VALUES(:pk,:item,:stock,:minimum)"
                    ), {"pk": pk, "item": item, "stock": stock, "minimum": minimum})
            config = visual.VisualizationDefinition(
                title="Inventario crítico", visualization="bar",
                table="inventario", metric="stock", aggregation="sum",
                group_by="nombre", group_by_table="productos",
                group_by_identity="id",
                filters=[visual.VisualizationFilter(
                    table="inventario", column="stock",
                    operator="lte_field", value="stock_minimo",
                )], sort_direction="asc", limit=50,
            )
            with patch.object(visual, "inspect_database", return_value=schema):
                with patch.object(visual.database_manager, "status",
                                  return_value={"provider": "excel"}):
                    sql = visual.build_visualization_query(config)
            self.assertIn('"inventario"."stock" <= "inventario"."stock_minimo"', sql)
            with engine.connect() as conn:
                rows = [dict(row) for row in conn.execute(text(sql)).mappings()]
            self.assertEqual([0, 3, 8], [int(row["value"]) for row in rows])
            self.assertEqual(["Monitor (#3)", "Teclado (#1)", "Monitor (#4)"],
                             [row["dimension"] for row in rows])
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

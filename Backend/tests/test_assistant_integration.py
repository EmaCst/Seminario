"""End-to-end Kenneth tests: real HTTP route, real SQLite and real schema.

The only mocked dependency is Ollama for deterministic cases. Everything else,
including FastAPI, detection, semantic mapping, SQL generation from metadata,
SQLAlchemy execution and answer formatting, uses the actual application code.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.main import app
from app.quality.fixtures import DOMAINS, connected_fixture
from app.security.sql_validator import SQLValidationError, validate_sql


class HttpIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def ask(self, question, history=None):
        result = self.client.post("/ask-db", json={
            "question": question, "history": history or [],
        })
        self.assertEqual(200, result.status_code, result.text)
        payload = result.json()
        self.assertEqual(question, payload.get("question"))
        return payload

    def test_detect_ten_domains_from_real_sqlite_schema(self):
        for fixture in DOMAINS:
            with self.subTest(domain=fixture.domain), connected_fixture(fixture):
                domain_response = self.client.get("/api/database/domain")
                self.assertEqual(200, domain_response.status_code,
                                 domain_response.text)
                detected = domain_response.json()
                self.assertEqual(fixture.domain, detected["primary_domain"],
                                 detected)
                self.assertFalse(detected["ambiguous"], detected)

                semantic_response = self.client.get("/api/database/semantic-model")
                self.assertEqual(200, semantic_response.status_code,
                                 semantic_response.text)
                semantic = semantic_response.json()["semantic_model"]
                self.assertEqual(fixture.domain, semantic["domain"])
                self.assertFalse(semantic["ambiguous_domain"], semantic)
                self.assertIn(fixture.primary_role, semantic["entities"], semantic)
                entity = semantic["entities"][fixture.primary_role]
                self.assertEqual(fixture.primary_table, entity["table"])
                self.assertFalse(entity["ambiguous"], entity)

    def test_all_ten_domains_count_compare_and_followup_via_http(self):
        for fixture in DOMAINS:
            with self.subTest(domain=fixture.domain), connected_fixture(fixture):
                with patch("app.services.assistant_service.generate_sql",
                           side_effect=AssertionError(
                               "A verified intent must never call Ollama")):
                    request = f"cuantas {fixture.question_term} hubo en junio"
                    june = self.ask(request)
                    self.assertEqual("analytics", june["mode"], june)
                    self.assertEqual(2, june["data"][0]["total"], june)
                    self.assertIn("junio de 2026", june["answer"])
                    feb = self.ask("¿y en febrero?", history=[
                        {"role": "user", "content": request},
                        {"role": "assistant", "content": june["answer"]},
                    ])
                    self.assertEqual("analytics", feb["mode"], feb)
                    self.assertEqual(1, feb["data"][0]["total"], feb)
                    compare = self.ask(
                        f"diferencia de {fixture.question_term} entre junio y febrero")
                    self.assertEqual("analytics", compare["mode"], compare)
                    totals = {row["month"]: row["total"] for row in compare["data"]}
                    self.assertEqual({6: 2, 2: 1}, totals)
                    self.assertIn("diferencia", compare["answer"].lower())

    def test_known_amounts_only_in_supported_domains(self):
        for fixture in DOMAINS:
            if fixture.amount_column is None:
                continue
            with self.subTest(domain=fixture.domain), connected_fixture(fixture):
                with patch("app.services.assistant_service.generate_sql",
                           side_effect=AssertionError("Known financial metric should not call Gemma")):
                    response = self.ask(
                        f"monto total de {fixture.question_term} en junio")
                self.assertEqual("analytics", response["mode"], response)
                self.assertEqual(500.0, response["data"][0]["total"], response)
                self.assertIn("500.00", response["answer"])

    def test_retail_complete_conversation_with_ground_truth(self):
        retail = next(item for item in DOMAINS if item.domain == "retail")
        with connected_fixture(retail) as engine:
            recorded_sql = []
            def capture(_conn, _cursor, statement, _params, _context, _executemany):
                recorded_sql.append(statement.strip().lower())
            event.listen(engine, "before_cursor_execute", capture)
            try:
                with patch("app.services.assistant_service.generate_sql",
                           side_effect=AssertionError("Retail metric must not use LLM")):
                    greeting = self.ask("hola keneth")
                    self.assertEqual("conversation", greeting["mode"])
                    self.assertEqual([], greeting["data"])

                    sales = self.ask("dime las ventas de junio")
                    self.assertEqual("analytics", sales["mode"], sales)
                    self.assertEqual(500, sales["data"][0]["total"])

                    count = self.ask("cuántas ventas hubo en junio")
                    self.assertEqual(2, count["data"][0]["total"])

                    units = self.ask("unidades vendidas en junio")
                    self.assertEqual(5, units["data"][0]["total"])

                    product = self.ask("dime el producto más vendido de junio")
                    self.assertEqual("Café", product["data"][0]["product"])
                    self.assertEqual(3, product["data"][0]["total"])

                    customer = self.ask("dime nuestro meyor cliente")
                    self.assertEqual("Ana", customer["data"][0]["customer"])
                    self.assertEqual(390, customer["data"][0]["total"])

                    difference = self.ask(
                        "diferencia en ventas entre junio y febrero")
                    self.assertEqual({6: 500, 2: 100},
                                     {v["month"]: v["total"]
                                      for v in difference["data"]})
                    attribution = self.ask("qué producto marcó esa diferencia",
                                           history=[
                                               {"role": "user",
                                                "content": "diferencia en ventas entre junio y febrero"},
                                               {"role": "assistant",
                                                "content": difference["answer"]},
                                           ])
                    self.assertEqual("Pan", attribution["data"][0]["product"])
                    self.assertEqual(210, attribution["data"][0]["difference"])
                self.assertTrue(recorded_sql)
                # Read-only queries are checked excluding SQLite introspection.
                self.assertFalse(any(item.startswith(("insert ", "update ", "delete ",
                                                      "drop ", "alter ", "create "))
                                     for item in recorded_sql))
            finally:
                event.remove(engine, "before_cursor_execute", capture)

    def test_sql_read_only_guard_against_fixture(self):
        retail = next(item for item in DOMAINS if item.domain == "retail")
        with connected_fixture(retail):
            with self.assertRaises(SQLValidationError):
                validate_sql("DELETE FROM ventas")
            with self.assertRaises(SQLValidationError):
                validate_sql("SELECT * FROM tabla_inventada")
            self.assertTrue(validate_sql("SELECT nombre FROM productos"))


if __name__ == "__main__":
    unittest.main()

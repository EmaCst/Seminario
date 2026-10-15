"""Ten-domain regression suite: counts, dates, money and safety gates.

SQLite is used as the deterministic fixture; the SQL builder also emits
provider-specific year/month expressions for PostgreSQL and SQL Server.
"""
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine

from app.services import assistant_domain_analytics as domain
from app.services import assistant_analytics as retail
from app.services.assistant_router import route_request


CASES = (
    ("retail", "sales", "ventas"),
    ("education", "enrollments", "inscripciones"),
    ("healthcare", "appointments", "citas"),
    ("transportation", "trips", "viajes"),
    ("hospitality", "reservations", "reservas"),
    ("restaurant", "orders", "pedidos"),
    ("professional_services", "invoices", "facturas"),
    ("finance_accounting", "transactions", "transacciones"),
    ("manufacturing", "production_orders", "ordenes de produccion"),
    ("human_resources", "payroll", "nomina"),
)


def fake_semantic(business: str, role: str) -> dict:
    return {
        "domain": business, "ambiguous_domain": False,
        "entities": {role: {
            "table": "records", "ambiguous": False, "confidence": "high",
            "columns": {"id": "id", "date": "fecha", "total": "total",
                        "amount": "total", "status": "estado"},
        }},
    }


class DomainCoverageTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE records (id INTEGER PRIMARY KEY, fecha TEXT, total REAL, estado TEXT)")
            connection.exec_driver_sql(
                "INSERT INTO records VALUES (1,'2026-02-11',100,'pendiente'),"
                "(2,'2026-06-09',250,'confirmado'),(3,'2026-06-21',350,'confirmado')")
        self.patches = [
            patch.object(domain, "get_connection", side_effect=lambda: self.engine.connect()),
            patch.object(domain, "_provider", return_value="excel"),
            patch.object(domain, "_quote", side_effect=lambda value: '"' + value.replace('"', '""') + '"'),
            patch.object(retail, "_provider", return_value="excel"),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.engine.dispose()

    def test_all_ten_domains_count_month(self):
        for business, role, word in CASES:
            with self.subTest(domain=business):
                semantic = fake_semantic(business, role)
                request = domain.classify_domain_question(
                    f"cuantos {word} en junio", [], semantic)
                self.assertIsNotNone(request)
                self.assertEqual("month", request.operation)
                result = domain.execute_domain_question(request, semantic)
                self.assertIn("2 registros", result["answer"])
                self.assertIn("junio de 2026", result["answer"])

    def test_all_ten_domains_count_all(self):
        for business, role, word in CASES:
            with self.subTest(domain=business):
                semantic = fake_semantic(business, role)
                request = domain.classify_domain_question(f"cuantos {word} hay", [], semantic)
                result = domain.execute_domain_question(request, semantic)
                self.assertIn("3 registros", result["answer"])

    def test_all_ten_domains_compare_periods(self):
        for business, role, word in CASES:
            with self.subTest(domain=business):
                semantic = fake_semantic(business, role)
                request = domain.classify_domain_question(
                    f"diferencia de {word} entre junio y febrero", [], semantic)
                self.assertIsNotNone(request)
                self.assertEqual("compare", request.operation)
                result = domain.execute_domain_question(request, semantic)
                self.assertIn("1 registros", result["answer"])

    def test_money_is_not_automatically_available_for_every_role(self):
        for business, role, word in CASES:
            semantic = fake_semantic(business, role)
            request = domain.classify_domain_question(
                f"importe de {word} de junio", [], semantic)
            with self.subTest(domain=business):
                if (business, role) in domain.MONETARY_ROLES:
                    self.assertIsNotNone(request)
                    result = domain.execute_domain_question(request, semantic)
                    self.assertIn("600.00", result["answer"])
                else:
                    self.assertIsNone(request)

    def test_peak_uses_true_prior_calendar_month(self):
        semantic = fake_semantic("healthcare", "appointments")
        query = domain.classify_domain_question(
            "mes con mas citas comparado con el anterior", [], semantic)
        self.assertEqual("peak", query.operation)
        answer = domain.execute_domain_question(query, semantic)
        self.assertIn("junio de 2026", answer["answer"])
        self.assertIn("No hay registros del mes calendario inmediatamente anterior", answer["answer"])

        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO records VALUES (4,'2026-05-11',60,'pendiente')")
        answer = domain.execute_domain_question(query, semantic)
        self.assertIn("mayo de 2026", answer["answer"])
        self.assertIn("la diferencia fue 1 registros", answer["answer"])

    def test_requested_count_not_monetary_amount(self):
        semantic = fake_semantic("professional_services", "payments")
        count = domain.classify_domain_question(
            "cuantos pagos de junio", [], semantic)
        amount = domain.classify_domain_question(
            "monto total de pagos de junio", [], semantic)
        self.assertEqual("count", count.metric)
        self.assertEqual("amount", amount.metric)
        self.assertIn("2 registros", domain.execute_domain_question(count, semantic)["answer"])
        self.assertIn("600.00", domain.execute_domain_question(amount, semantic)["answer"])

    def test_status_month_is_filtered(self):
        semantic = fake_semantic("healthcare", "appointments")
        request = domain.classify_domain_question(
            "distribucion por estado de citas en febrero", [], semantic)
        self.assertEqual("status", request.operation)
        result = domain.execute_domain_question(request, semantic)
        self.assertIn("pendiente: 1", result["answer"])
        self.assertNotIn("confirmado", result["answer"])

    def test_unsupported_predicates_are_not_silently_dropped(self):
        semantic = fake_semantic("hospitality", "reservations")
        for question in (
            "cuantas reservas canceladas en junio",
            "cuantas reservas en 2026",
            "reservas del cliente Ana en junio",
            "promedio de reservas de junio",
            "ocupacion de habitaciones en junio",
            "cuantas reservas entre junio y julio",
            "cuantas reservas del 12 de junio",
            "cuantas reservas del hotel Central en junio",
        ):
            with self.subTest(question=question):
                self.assertIsNone(domain.classify_domain_question(question, [], semantic))

    def test_no_guesses_when_domain_or_entity_uncertain(self):
        semantic = fake_semantic("healthcare", "appointments")
        semantic["ambiguous_domain"] = True
        with patch.object(domain, "inspect_semantic_model", return_value={"semantic_model": semantic}):
            answer, business = domain.run_domain_analytics("cuantas citas de junio")
        self.assertIsNone(answer)
        self.assertIsNone(business)
        semantic["ambiguous_domain"] = False
        semantic["entities"]["appointments"]["ambiguous"] = True
        self.assertIsNone(domain.classify_domain_question("cuantas citas de junio", [], semantic))

    def test_multi_entity_filter_requires_sql_not_total_count(self):
        semantic = fake_semantic("healthcare", "appointments")
        semantic["entities"]["patients"] = {
            "table": "records", "ambiguous": False, "columns": {"date": "fecha"}}
        request = domain.classify_domain_question(
            "cuantas citas de pacientes en junio", [], semantic)
        self.assertIsNone(request)

    def test_followup_uses_same_domain_role(self):
        semantic = fake_semantic("transportation", "trips")
        history = [{"role": "user", "content": "cuantos viajes hubo en junio"}]
        request = domain.classify_domain_question("y en febrero?", history, semantic)
        self.assertEqual("trips", request.role)
        self.assertEqual((2,), request.months)

    def test_generic_domain_preempts_llm_when_verifiable(self):
        from app.services.assistant_service import ask_database
        semantic = fake_semantic("education", "enrollments")
        with patch.object(domain, "inspect_semantic_model",
                          return_value={"semantic_model": semantic}):
            with patch("app.services.assistant_service.generate_sql",
                       side_effect=AssertionError("Must not call Gemma")):
                answer = ask_database("cuantas inscripciones en junio")
        self.assertEqual("analytics", answer["mode"])
        self.assertIn("2 registros", answer["answer"])

    def test_nonretail_product_not_routed_to_retail_handler(self):
        from app.services.assistant_service import ask_database
        semantic = fake_semantic("manufacturing", "products")
        with patch.object(domain, "inspect_semantic_model",
                          return_value={"semantic_model": semantic}):
            with patch("app.services.assistant_service.run_verified_analytics",
                       side_effect=AssertionError("Retail shortcut is unsafe")):
                with patch("app.services.assistant_service.generate_sql",
                           return_value="SELECT 1 AS result"):
                    with patch("app.services.assistant_service.execute_query",
                               return_value=[{"result": 1}]):
                        result = ask_database("producto más vendido de junio")
        self.assertEqual("sql", result["mode"])

    def test_sql_dialect_date_functions(self):
        with patch.object(retail, "_provider", return_value="sqlserver"):
            self.assertIn("YEAR(", retail._year_expr("t.fecha"))
        with patch.object(retail, "_provider", return_value="postgresql"):
            self.assertIn("EXTRACT(YEAR", retail._year_expr("t.fecha"))
        with patch.object(retail, "_provider", return_value="excel"):
            self.assertIn("strftime", retail._year_expr("t.fecha"))


if __name__ == "__main__":
    unittest.main()

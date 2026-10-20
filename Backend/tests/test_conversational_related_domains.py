"""Domain coverage for safe conversational visualization dimensions."""
import unittest
from unittest.mock import patch

from app.visualizations import conversational_drafts as drafts


CASE_STUDIES = [
    ("retail", "sales", "Ventas", "ventas", "customers", "Clientes",
     "clientes", "Crea una gráfica de ventas por cliente"),
    ("education", "enrollments", "Inscripciones", "inscripciones", "courses", "Cursos",
     "cursos", "Crea una gráfica de inscripciones por curso"),
    ("healthcare", "appointments", "Citas", "citas", "doctors", "Médicos",
     "medicos", "Crea una gráfica de citas por médico"),
    ("transportation", "trips", "Viajes", "viajes", "drivers", "Conductores",
     "conductores", "Crea una gráfica de viajes por conductor"),
    ("hospitality", "reservations", "Reservas", "reservas", "rooms", "Habitaciones",
     "habitaciones", "Crea una gráfica de reservas por habitación"),
    ("restaurant", "orders", "Órdenes", "ordenes", "tables", "Mesas",
     "mesas", "Crea una gráfica de órdenes por mesa"),
    ("professional_services", "invoices", "Facturas", "facturas", "clients", "Clientes",
     "clientes", "Crea una gráfica de facturas por cliente"),
    ("finance_accounting", "transactions", "Transacciones", "transacciones", "accounts", "Cuentas",
     "cuentas", "Crea una gráfica de transacciones por cuenta"),
    ("manufacturing", "production_orders", "Órdenes de producción", "ordenes_produccion",
     "products", "Productos", "productos", "Crea una gráfica de órdenes de producción por producto"),
    ("human_resources", "payroll", "Nómina", "nomina", "employees", "Empleados",
     "empleados", "Crea una gráfica de nómina por empleado"),
]


def make_catalog(domain, role, label, fact_table, parent_role, parent_label, parent_table):
    fact = {
        "key": role, "semantic_role": role,
        "label": label, "table": fact_table,
        "primary_key": ["id"],
        "fields": [{"key": "id", "label": "Identificador", "semantic": "id"}],
        "dimensions": [],
        "metrics": [{
            "key": "total", "label": "Total", "semantic": "total",
            "kind": "number", "aggregations": ["sum", "avg", "count"],
        }] if role == "sales" else [],
    }
    parent = {
        "key": parent_role, "semantic_role": parent_role,
        "label": parent_label, "table": parent_table,
        "primary_key": ["id"],
        "fields": [{"key": "nombre", "label": "Nombre", "semantic": "name"}],
        "dimensions": [{"key": "nombre", "label": "Nombre", "semantic": "name"}],
        "metrics": [],
    }
    return {
        "domain": domain, "entities": [fact, parent],
        "relationships": [{
            "from_table": fact_table, "from_column": "parent_id",
            "to_table": parent_table, "to_column": "id",
        }],
    }


class ConversationalRelatedBusinessTests(unittest.TestCase):
    def test_grouping_by_related_business_entity_across_ten_domains(self):
        for case in CASE_STUDIES:
            domain, role, label, fact, parent_role, parent_label, parent, phrase = case
            with self.subTest(domain=domain):
                db = make_catalog(domain, role, label, fact, parent_role, parent_label, parent)
                with patch.object(drafts, "get_semantic_visualization_catalog", return_value=db):
                    with patch.object(drafts, "preview_visualization",
                                      return_value={"data": [{"dimension": "A", "value": 2}]}):
                        with patch.object(drafts.database_manager, "status",
                                          return_value={"provider": "excel", "database": domain}):
                            result = drafts.interpret_visualization_request(phrase)
                definition = result["definition"]
                self.assertEqual(fact, definition["table"])
                self.assertEqual(parent, definition["group_by_table"])
                self.assertEqual("nombre", definition["group_by"])
                self.assertEqual("id", definition["group_by_identity"])
                self.assertEqual("sum" if role == "sales" else "count", definition["aggregation"])

    def test_missing_verified_relation_does_not_guess_a_join(self):
        db = make_catalog(
            "healthcare", "appointments", "Citas", "citas",
            "doctors", "Médicos", "medicos",
        )
        db["relationships"] = []
        with patch.object(drafts, "get_semantic_visualization_catalog", return_value=db):
            with self.assertRaisesRegex(ValueError, "dimensión"):
                drafts.interpret_visualization_request(
                    "Crea una gráfica de citas por médico"
                )

    def test_quarterly_area_request_uses_true_time_bucket(self):
        db = make_catalog(
            "education", "enrollments", "Inscripciones", "inscripciones",
            "courses", "Cursos", "cursos",
        )
        date_field = {"key": "fecha", "label": "Fecha", "semantic": "date", "kind": "date"}
        db["entities"][0]["fields"].append(date_field)
        db["entities"][0]["dimensions"].append(date_field)
        with patch.object(drafts, "get_semantic_visualization_catalog", return_value=db):
            with patch.object(drafts, "preview_visualization",
                              return_value={"data": [{"dimension": "2026-Q1", "value": 3}]}):
                with patch.object(drafts.database_manager, "status",
                                  return_value={"provider": "excel", "database": "educacion"}):
                    result = drafts.interpret_visualization_request(
                        "Crea una gráfica de área de inscripciones por trimestre de 2026"
                    )
        self.assertEqual("area", result["definition"]["visualization"])
        self.assertEqual("quarter", result["definition"]["time_granularity"])
        self.assertEqual("Trimestre y año", result["axes"]["x"])


if __name__ == "__main__":
    unittest.main()

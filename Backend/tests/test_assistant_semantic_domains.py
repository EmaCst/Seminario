"""Check real domain detection and semantic mapping, without database fixtures."""
import unittest

from app.analysis.business_domain_detector import detect_business_domains
from app.analysis.semantic_mapper_v2 import ROLE_PROFILES, build_semantic_model
from app.database.schema import ColumnSchema, DatabaseSchema, TableSchema


CASES = {
    "retail": (("ventas", "productos", "inventario", "clientes"), "sales"),
    "education": (("estudiantes", "docentes", "cursos", "inscripciones"), "enrollments"),
    "healthcare": (("pacientes", "medicos", "citas", "diagnosticos"), "appointments"),
    "transportation": (("vehiculos", "rutas", "viajes", "conductores"), "trips"),
    "hospitality": (("habitaciones", "reservas", "huespedes", "estadias"), "reservations"),
    "restaurant": (("platos", "mesas", "pedidos", "ingredientes"), "orders"),
    "professional_services": (("servicios", "clientes", "proyectos", "facturas"), "invoices"),
    "finance_accounting": (("cuentas", "transacciones", "asientos", "libro_mayor"), "transactions"),
    "manufacturing": (("orden_produccion", "materiales", "maquinas", "lotes"), "production_orders"),
    "human_resources": (("empleados", "nomina", "departamentos", "turnos"), "payroll"),
}


def schema_from_tables(table_names: tuple[str, ...]) -> DatabaseSchema:
    schema = DatabaseSchema(database="domain_fixture")
    for name in table_names:
        # Synthetic columns are plausible but not treated as real records.
        fields = ("id", "nombre", "fecha", "total", "estado")
        schema.tables[name] = TableSchema(
            name=name, primary_key=["id"],
            columns=[ColumnSchema(field, "VARCHAR", True) for field in fields],
        )
    return schema


class SemanticDomainsTests(unittest.TestCase):
    def test_ten_domain_profiles_exist(self):
        self.assertEqual(set(CASES), set(ROLE_PROFILES))

    def test_domain_detector_and_mapper_use_ten_schema_families(self):
        for expected, (tables, required_role) in CASES.items():
            with self.subTest(domain=expected):
                schema = schema_from_tables(tables)
                domain = detect_business_domains(schema)
                self.assertEqual(expected, domain["primary_domain"])
                self.assertFalse(domain["ambiguous"])
                mapped = build_semantic_model(schema, domain)
                self.assertEqual(expected, mapped["domain"])
                self.assertIn(required_role, mapped["entities"])
                self.assertIn(mapped["entities"][required_role]["table"], tables)

    def test_unknown_schema_does_not_invent_domain(self):
        schema = schema_from_tables(("foo_opaque", "bar_opaque"))
        discovered = detect_business_domains(schema)
        self.assertIsNone(discovered["primary_domain"])
        self.assertEqual({}, build_semantic_model(schema, discovered)["entities"])


if __name__ == "__main__":
    unittest.main()

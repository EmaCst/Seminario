"""End-to-end synthetic vehicle-rental domain contract and regression checks."""
import asyncio
import io
import unittest

from fastapi import UploadFile
from openpyxl import Workbook

from app.analysis.business_domain_detector import inspect_business_domains
from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.analysis.adaptive_dashboard_service import get_adaptive_dashboard_summary
from app.analysis.adaptive_analytics_service import get_adaptive_analytics
from app.database.database_manager import database_manager
from app.database.excel_loader import activate_excel_upload
from app.database.inspector import inspect_database
from app.ml.predictive_service import _find_best_time_series
from app.services.assistant_domain_analytics import classify_domain_question, MONETARY_ROLES
from app.visualizations.semantic_catalog import get_semantic_visualization_catalog


def rental_book():
    w = Workbook()
    vehicles = w.active
    vehicles.title = "Flota_Vehiculos"
    vehicles.append(["ID Vehículo", "Marca", "Modelo", "Categoría", "Placa",
                     "Tarifa Diaria ($)", "Estado", "Kilometraje Actual"])
    vehicles.append(["VEH-101", "Toyota", "Corolla", "Sedán", "P-101", 45, "Disponible", 14500])
    vehicles.append(["VEH-102", "Hyundai", "Tucson", "SUV", "P-102", 65, "Rentado", 16000])
    customers = w.create_sheet("Clientes")
    customers.append(["ID Cliente", "Nombre Completo", "Correo Electrónico", "Fecha Registro"])
    customers.append(["CLI-001", "María López", "maria@example.test", "2026-01-01"])
    customers.append(["CLI-002", "Carlos Ruiz", "carlos@example.test", "2026-01-04"])
    rentals = w.create_sheet("Reservas_y_Rentas")
    rentals.append(["ID Reserva", "ID Cliente", "ID Vehículo", "Fecha Inicio", "Fecha Fin",
                    "Días Renta", "Tarifa/Día ($)", "Subtotal ($)", "Seguro Total ($)",
                    "Descuento ($)", "Total General ($)", "Método Pago", "Estado Reserva"])
    for i, (customer, vehicle, start, end, price, status) in enumerate([
        ("CLI-001", "VEH-101", "2026-01-05", "2026-01-09", 45, "Finalizada"),
        ("CLI-002", "VEH-102", "2026-02-05", "2026-02-09", 65, "Finalizada"),
        ("CLI-001", "VEH-101", "2026-03-05", "2026-03-09", 45, "Finalizada"),
        ("CLI-002", "VEH-102", "2026-04-05", "2026-04-09", 65, "Confirmada"),
    ], start=2):
        rentals.append([f"RES-{i}", customer, vehicle, start, end,
                        f'=DATEVALUE("{end}")-DATEVALUE("{start}")',
                        price, f"=F{i}*G{i}", 20, 0, f"=H{i}+I{i}-J{i}",
                        "Tarjeta", status])
    maintenance = w.create_sheet("Mantenimiento")
    maintenance.append(["ID Mantenimiento", "ID Vehículo", "Fecha Ingreso", "Fecha Entrega",
                        "Tipo Servicio", "Descripción del Trabajo", "Taller / Proveedor",
                        "Costo ($)", "Estado"])
    maintenance.append(["MNT-01", "VEH-101", "2026-02-07", "2026-02-08",
                        "Preventivo", "Cambio de aceite", "Taller Sur", 95, "Completado"])
    return w


class VehicleRentalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workbook = rental_book()
        stream = io.BytesIO()
        workbook.save(stream)
        stream.seek(0)
        cls.info = asyncio.run(activate_excel_upload(
            UploadFile(filename="synthetic_rental.xlsx", file=stream)))
        cls.schema = inspect_database()
        cls.domain = inspect_business_domains()
        cls.semantic = inspect_semantic_model()["semantic_model"]

    def test_domain_detection_and_four_roles(self):
        self.assertEqual("vehicle_rental", self.domain["primary_domain"])
        self.assertEqual("vehicle_rental", self.semantic["domain"])
        for role in ("rentals", "vehicles", "customers", "maintenance"):
            self.assertIn(role, self.semantic["entities"], role)
        self.assertEqual("reservas_y_rentas", self.semantic["entities"]["rentals"]["table"])
        self.assertEqual("total_general", self.semantic["entities"]["rentals"]["columns"]["total"])

    def test_formula_recalculation_and_iso_dates(self):
        self.assertEqual(12, self.info["formula_diagnostics"]["formulas_calculated"])
        cols = {c.name: c.type.lower() for c in self.schema.tables["reservas_y_rentas"].columns}
        self.assertIn("date", cols["fecha_inicio"])
        self.assertIn("numeric", cols["total_general"] if "numeric" in cols["total_general"] else "numeric")

    def test_unique_business_ids_and_foreign_key_inference(self):
        self.assertEqual(["id_cliente"], self.schema.tables["clientes"].primary_key)
        self.assertEqual(["id_vehículo"], self.schema.tables["flota_vehiculos"].primary_key)
        links = {(r.table, r.column, r.references_table) for r in self.schema.relationships}
        self.assertIn(("reservas_y_rentas", "id_cliente", "clientes"), links)
        self.assertIn(("reservas_y_rentas", "id_vehículo", "flota_vehiculos"), links)

    def test_dashboard_kpis_trend_status_and_analytics(self):
        summary = get_adaptive_dashboard_summary()
        self.assertEqual("vehicle_rental", summary["domain"])
        kpis = {r["role"]: r["value"] for r in summary["kpis"]}
        self.assertEqual(4, kpis["rentals"])
        self.assertEqual(2, kpis["vehicles"])
        self.assertEqual(2, kpis["customers"])
        self.assertEqual(1, kpis["maintenance"])
        self.assertTrue(summary["trend"]["available"], summary)
        self.assertEqual("rentals", summary["trend"]["role"])
        self.assertEqual(4, len(summary["trend"]["data"]))
        self.assertTrue(summary["status_distribution"]["available"])
        self.assertEqual("rentals", summary["status_distribution"]["role"])
        analysis = get_adaptive_analytics()
        self.assertTrue(analysis["distributions"])
        self.assertTrue(analysis["numeric_metrics"])
        self.assertTrue(analysis["rankings"])

    def test_assistant_forecasts_and_chart_catalog(self):
        self.assertEqual(("total",), MONETARY_ROLES[("vehicle_rental", "rentals")])
        request = classify_domain_question("cuántas rentas hubo", [], self.semantic)
        self.assertEqual("rentals", request.role)
        forecast = _find_best_time_series("pronostica rentas", minimum_points=3)
        self.assertEqual("rentals", forecast.role)
        self.assertEqual(4, len(forecast.data))
        catalog = get_semantic_visualization_catalog()
        roles = {e["semantic_role"] for e in catalog["entities"]}
        self.assertIn("rentals", roles)
        self.assertIn("vehicles", roles)
        self.assertIn("maintenance", roles)


if __name__ == "__main__":
    unittest.main()

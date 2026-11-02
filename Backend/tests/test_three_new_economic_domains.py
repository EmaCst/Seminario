"""Synthetic end-to-end Excel imports for three new economic sectors."""
import asyncio
import io
import unittest

from fastapi import UploadFile
from openpyxl import Workbook

from app.analysis.business_domain_detector import inspect_business_domains
from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.analysis.adaptive_dashboard_service import get_adaptive_dashboard_summary
from app.database.excel_loader import activate_excel_upload


def import_sheets(sheets):
    book = Workbook()
    book.remove(book.active)
    for sheet_name, rows in sheets.items():
        sheet = book.create_sheet(sheet_name)
        for row in rows:
            sheet.append(row)
    data = io.BytesIO()
    book.save(data)
    data.seek(0)
    return asyncio.run(activate_excel_upload(
        UploadFile(filename="example_sector.xlsx", file=data)
    ))


class ThreeNewSectorTests(unittest.TestCase):
    def test_real_estate_and_calculated_rent_amount(self):
        info = import_sheets({
            "Inmuebles": [
                ["ID Inmueble", "Direccion", "Estado", "Precio Venta"],
                ["INM-1", "Avenida 1", "Arrendado", 140000],
            ],
            "Inquilinos": [
                ["ID Inquilino", "Nombre"],
                ["TEN-1", "Lucia"],
            ],
            "Arrendamientos": [
                ["ID Arrendamiento", "ID Inmueble", "ID Inquilino",
                 "Fecha Inicio", "Estado Contrato", "Renta Mensual",
                 "Total Cobrado"],
                ["ARR-1", "INM-1", "TEN-1", "2026-01-01", "Activo",
                 500, "=F2*3"],
            ],
            "Agentes_Inmobiliarios": [
                ["ID Agente", "Nombre"],
                ["AGE-1", "Agente 1"],
            ],
        })
        self.assertEqual("real_estate", inspect_business_domains()["primary_domain"])
        model = inspect_semantic_model()["semantic_model"]
        self.assertTrue({"properties", "leases", "tenants", "agents"}.issubset(model["entities"]))
        report = get_adaptive_dashboard_summary()
        self.assertTrue(report["trend"]["available"], report)
        self.assertTrue(report["status_distribution"]["available"], report)
        self.assertEqual(1500.0, next(
            metric["value"] for metric in report["value_metrics"]
            if metric["role"] == "leases" and metric["field"] == "total"
        ))
        self.assertEqual(1, info["formula_diagnostics"]["formulas_calculated"])

    def test_construction_with_budgets_and_work_progress(self):
        import_sheets({
            "Obras": [
                ["ID Obra", "Nombre Obra", "Fecha Inicio",
                 "Estado Obra", "Costo Real", "Porcentaje Avance"],
                ["OB-1", "Edificio", "2026-03-01", "En proceso", 42000, 60],
            ],
            "Presupuestos_Obra": [
                ["ID Presupuesto", "Monto Presupuestado"],
                ["P-1", 50000],
            ],
            "Contratistas": [
                ["ID Contratista", "Nombre"],
                ["C-1", "Empresa de obra"],
            ],
            "Materiales_Obra": [
                ["ID Material", "Nombre", "Cantidad Consumida", "Costo Total"],
                ["M-1", "Cemento", 80, 2000],
            ],
        })
        self.assertEqual("construction", inspect_business_domains()["primary_domain"])
        model = inspect_semantic_model()["semantic_model"]
        self.assertTrue({"projects", "budgets", "contractors", "materials"}.issubset(
            model["entities"]), model)
        report = get_adaptive_dashboard_summary()
        self.assertTrue(report["trend"]["available"], report)
        self.assertTrue(report["status_distribution"]["available"], report)
        self.assertEqual(42000.0, next(
            metric["value"] for metric in report["value_metrics"]
            if metric["role"] == "projects" and metric["field"] == "amount"
        ))
        self.assertEqual(60, next(
            metric["value"] for metric in report["value_metrics"]
            if metric["role"] == "projects" and metric["field"] == "value"
        ))

    def test_farms_with_crops_and_calculated_harvest(self):
        info = import_sheets({
            "Parcelas": [
                ["ID Parcela", "Nombre", "Hectareas"],
                ["PAR-1", "Lote Norte", 2],
            ],
            "Cultivos": [
                ["ID Cultivo", "ID Parcela", "Tipo Cultivo", "Fecha Siembra"],
                ["CUL-1", "PAR-1", "Maiz", "2026-01-01"],
            ],
            "Cosechas": [
                ["ID Cosecha", "ID Cultivo", "Fecha Cosecha",
                 "Kilos Cosechados", "Estado"],
                ["COS-1", "CUL-1", "2026-05-05", "=120+180", "Completado"],
            ],
            "Ganado": [
                ["ID Animal", "Especie", "Peso"],
                ["ANI-1", "Bovino", 280],
            ],
        })
        self.assertEqual("agriculture", inspect_business_domains()["primary_domain"])
        model = inspect_semantic_model()["semantic_model"]
        self.assertTrue({"fields", "crops", "harvests", "livestock"}.issubset(
            model["entities"]), model)
        report = get_adaptive_dashboard_summary()
        self.assertTrue(report["trend"]["available"], report)
        self.assertTrue(report["status_distribution"]["available"], report)
        self.assertEqual(300.0, next(
            metric["value"] for metric in report["value_metrics"]
            if metric["role"] == "harvests" and metric["field"] == "quantity"
        ))
        self.assertEqual(1, info["formula_diagnostics"]["formulas_calculated"])


if __name__ == "__main__":
    unittest.main()

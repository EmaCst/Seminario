import io
import unittest

from fastapi import UploadFile
from openpyxl import Workbook

from app.database.formula_engine import FormulaEvaluator
from app.database.excel_loader import inspect_excel_upload


def sample():
    book = Workbook()
    data = book.active
    data.title = "Reservas_y_Rentas"
    data.append(["ID Reserva", "Días Renta", "Tarifa", "Subtotal", "Total"])
    data.append(["RES-5001", '=DATEVALUE("2026-09-05")-DATEVALUE("2026-09-01")', 45, "=B2*C2", "=D2+40"])
    data.append(["RES-5002", '=DATEVALUE("2026-09-12")-DATEVALUE("2026-09-05")', 150, "=B3*C3", "=D3+105"])
    fleet = book.create_sheet("Flota_Vehiculos")
    fleet.append(["ID Vehículo", "Categoría", "Estado", "Tarifa"])
    fleet.append(["VEH-101", "Sedán", "Disponible", 45])
    fleet.append(["VEH-102", "SUV Premium", "Rentado", 150])
    panel = book.create_sheet("Panel_Resumen")
    panel["A1"] = '=SUM(Reservas_y_Rentas!E2:E3)'
    panel["B1"] = '=COUNTIF(Flota_Vehiculos!C2:C3,"Rentado")'
    panel["C1"] = '=AVERAGEIF(Flota_Vehiculos!B2:B3,"*SUV*",Flota_Vehiculos!D2:D3)'
    return book


class FormulaEvaluationTests(unittest.TestCase):
    def test_calculate_rentals_cross_sheet_and_criteria(self):
        engine = FormulaEvaluator(sample())
        report = engine.calculate()
        self.assertEqual(report["formulas_detected"], 9)
        self.assertEqual(report["formulas_unresolved"], 0)
        self.assertEqual(engine.value("Reservas_y_Rentas", "B2"), 4)
        self.assertEqual(engine.value("Reservas_y_Rentas", "D2"), 180)
        self.assertEqual(engine.value("Reservas_y_Rentas", "E2"), 220)
        self.assertEqual(engine.value("Panel_Resumen", "A1"), 1375)
        self.assertEqual(engine.value("Panel_Resumen", "B1"), 1)
        self.assertEqual(engine.value("Panel_Resumen", "C1"), 150)

    def test_circular_unsupported_and_lazy_if(self):
        book = Workbook()
        ws = book.active
        ws["A1"] = "=B1+1"
        ws["B1"] = "=A1+1"
        ws["C1"] = '=HYPERLINK("https://example.com","click")'
        ws["D1"] = "=IF(FALSE,1/0,45)"
        ws["E1"] = "=IFERROR(1/0,12)"
        engine = FormulaEvaluator(book)
        result = engine.calculate()
        self.assertEqual(result["formulas_detected"], 5)
        self.assertEqual(result["formulas_calculated"], 2)
        self.assertEqual(result["formulas_unresolved"], 3)
        self.assertEqual(engine.value(ws.title, "D1"), 45)
        self.assertEqual(engine.value(ws.title, "E1"), 12)

    def test_actual_excel_import_preview_resolves_values(self):
        book = sample()
        buf = io.BytesIO()
        book.save(buf)
        buf.seek(0)
        upload = UploadFile(filename="renta.xlsx", file=buf)
        import asyncio
        info = asyncio.run(inspect_excel_upload(upload))
        self.assertEqual(info["formula_diagnostics"]["formulas_calculated"], 9)
        rentals = next(s for s in info["sheets"] if s["name"] == "Reservas_y_Rentas")
        self.assertEqual(rentals["preview"][0]["d_as_renta"], 4)
        self.assertEqual(rentals["preview"][0]["subtotal"], 180)
        self.assertEqual(rentals["preview"][0]["total"], 220)


if __name__ == "__main__":
    unittest.main()

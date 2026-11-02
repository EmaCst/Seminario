"""Regression tests: sales are optional, orders differ from shipments and sales."""
import asyncio
import io
import unittest

from fastapi import UploadFile
from openpyxl import Workbook

from app.analysis.adaptive_dashboard_service import get_adaptive_dashboard_summary
from app.analysis.business_domain_detector import inspect_business_domains
from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.database.excel_loader import activate_excel_upload


def activate(sheets, filename="operaciones.xlsx"):
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return asyncio.run(activate_excel_upload(
        UploadFile(filename=filename, file=stream)))


class SchemaAliasTests(unittest.TestCase):

    def test_orders_without_a_sales_table(self):
        info = activate({
            "Pedidos": [
                ("ID Pedido", "Fecha Pedido", "Estado Pedido", "Total Pedido", "ID Cliente"),
                ("P-1", "2026-01-03", "Pendiente", 100.0, "C-1"),
                ("P-2", "2026-02-03", "Enviado", 150.0, "C-2"),
            ]
        })
        self.assertEqual("excel", info["connection"]["provider"])
        self.assertEqual("retail", inspect_business_domains()["primary_domain"])
        semantic = inspect_semantic_model()["semantic_model"]
        self.assertIn("orders", semantic["entities"])
        self.assertNotIn("sales", semantic["entities"],
                         "Un pedido sin venta registrada no debe convertirse en ventas")
        self.assertEqual("total_pedido", semantic["entities"]["orders"]["columns"]["total"])
        dashboard = get_adaptive_dashboard_summary()
        self.assertEqual(2, dashboard["kpis"][0]["value"])
        self.assertEqual("orders", dashboard["trend"]["role"])
        self.assertTrue(dashboard["trend"]["available"])
        self.assertTrue(dashboard["status_distribution"]["available"])
        self.assertEqual(250.0, next(
            m["value"] for m in dashboard["value_metrics"]
            if m["role"] == "orders" and m["field"] == "total"
        ))

    def test_shipping_without_sales(self):
        activate({
            "Envios": [
                ("ID Envio", "Fecha Envio", "Estado Envio", "Numero Guia",
                 "Costo Envio", "ID Pedido", "ID Transportista"),
                ("E-1", "2026-01-03", "En tránsito", "G-001", 45.0, "P-1", "T-1"),
                ("E-2", "2026-02-03", "Entregado", "G-002", 35.0, "P-2", "T-1"),
            ],
            "Pedidos": [
                ("ID Pedido", "Fecha Pedido", "Estado Pedido", "Total Pedido"),
                ("P-1", "2026-01-02", "Preparado", 300.0),
                ("P-2", "2026-01-29", "Preparado", 120.0),
            ],
            "Transportistas": [
                ("ID Transportista", "Nombre"),
                ("T-1", "Mensajería Norte"),
            ],
        })
        self.assertEqual("logistics", inspect_business_domains()["primary_domain"])
        semantic = inspect_semantic_model()["semantic_model"]
        self.assertTrue({"shipments", "orders", "carriers"}.issubset(
            semantic["entities"].keys()), semantic)
        self.assertNotIn("sales", semantic["entities"])
        summary = get_adaptive_dashboard_summary()
        self.assertEqual("shipments", summary["trend"]["role"])
        self.assertEqual("shipments", summary["status_distribution"]["role"])
        self.assertEqual(2, next(
            k["value"] for k in summary["kpis"] if k["role"] == "shipments"))

    def test_single_shipment_table_is_enough(self):
        activate({
            "RegistroEnvios": [
                ("ID Envio", "Fecha Envio", "Estado Envio"),
                ("E-1", "2026-05-12", "Enviado"),
                ("E-2", "2026-05-14", "Entregado"),
            ],
        })
        domain = inspect_business_domains()
        self.assertEqual("logistics", domain["primary_domain"], domain)
        semantic = inspect_semantic_model()["semantic_model"]
        self.assertIn("shipments", semantic["entities"], semantic)
        self.assertTrue(get_adaptive_dashboard_summary()["trend"]["available"])

    def test_unclassified_source_keeps_real_tables_and_charts(self):
        activate({
            "Mediciones": [
                ("ID", "Fecha", "Estado", "Valor"),
                (1, "2026-01-01", "Bien", 10),
                (2, "2026-02-01", "Regular", 20),
            ]
        })
        self.assertIsNone(inspect_business_domains()["primary_domain"])
        semantic = inspect_semantic_model()["semantic_model"]
        self.assertEqual("general", semantic["domain"])
        self.assertEqual("insufficient", semantic["domain_confidence"])
        self.assertEqual("mediciones", semantic["entities"]["tabla_mediciones"]["table"])
        dashboard = get_adaptive_dashboard_summary()
        self.assertEqual(2, dashboard["kpis"][0]["value"])
        self.assertTrue(dashboard["trend"]["available"])
        self.assertTrue(dashboard["status_distribution"]["available"])

    def test_restaurant_stays_a_restaurant_with_orders(self):
        activate({
            "Platos": [("ID", "Nombre", "Precio"), (1, "Sopa", 10)],
            "Mesas": [("ID", "Numero", "Capacidad"), (1, "M1", 4)],
            "Pedidos": [
                ("ID Pedido", "Fecha Pedido", "Estado Pedido", "Total Pedido"),
                ("P-1", "2026-05-12", "Servido", 10),
            ],
            "Ingredientes": [("ID", "Nombre", "Cantidad"), (1, "Tomate", 10)],
        })
        self.assertEqual("restaurant", inspect_business_domains()["primary_domain"])


if __name__ == "__main__":
    unittest.main()

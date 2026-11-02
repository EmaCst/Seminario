"""E2E real Excel -> formula evaluator -> SQLite -> semantic -> dashboard.

The fixtures are synthetic. Each domain must recognize genuine business
entities and computed monetary/quantity values; no external database needed.
"""
import asyncio
import io
import unittest
from fastapi import UploadFile
from openpyxl import Workbook

from app.database.excel_loader import activate_excel_upload
from app.analysis.business_domain_detector import inspect_business_domains
from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.analysis.adaptive_dashboard_service import get_adaptive_dashboard_summary


FIXTURES = {
    "insurance": {
        "Polizas": [
            ["ID Poliza", "Fecha Emision", "Estado Poliza", "Prima Anual"],
            ["POL-1", "2026-01-15", "Activa", "=500+50"],
        ],
        "Siniestros": [
            ["ID Siniestro", "ID Poliza", "Fecha Siniestro", "Estado Siniestro", "Monto Indemnizado"],
            ["SIN-1", "POL-1", "2026-02-05", "Pagado", 175],
        ],
        "Coberturas": [["ID Cobertura", "Nombre Cobertura"], ["COB-1", "Daños"]],
        "Asegurados": [["ID Asegurado", "Nombre"], ["ASE-1", "María"]],
    },
    "pharmacy": {
        "Medicamentos": [["ID Medicamento", "Nombre Medicamento"], ["MED-1", "Paracetamol"]],
        "Lotes_Medicamentos": [
            ["ID Lote", "ID Medicamento", "Fecha Caducidad", "Cantidad Disponible"],
            ["LOT-1", "MED-1", "2027-01-01", 50],
        ],
        "Dispensaciones": [
            ["ID Dispensacion", "Fecha Dispensacion", "Estado", "Cantidad", "Total Venta"],
            ["DIS-1", "2026-02-05", "Entregado", 3, "=10*3"],
        ],
        "Farmacias": [["ID Farmacia", "Nombre"], ["FAR-1", "Central"]],
    },
    "saas": {
        "Suscripciones": [
            ["ID Suscripcion", "Fecha Inicio", "Estado Suscripcion", "Monto Recurrente"],
            ["SUB-1", "2026-02-05", "Activa", "=20*3"],
        ],
        "Planes_SaaS": [["ID Plan", "Nombre Plan", "Precio Mensual"], ["PLAN-1", "Pro", 60]],
        "Organizaciones": [["ID Organizacion", "Nombre"], ["ORG-1", "Empresa Alfa"]],
        "Tickets_Soporte": [
            ["ID Ticket", "Fecha Apertura", "Estado Ticket"],
            ["TCK-1", "2026-02-06", "Resuelto"],
        ],
    },
    "events": {
        "Eventos": [
            ["ID Evento", "Nombre Evento", "Fecha Evento", "Estado Evento", "Aforo"],
            ["EVE-1", "Concierto", "2026-02-05", "Confirmado", 50],
        ],
        "Entradas_Evento": [
            ["ID Entrada", "ID Evento", "Fecha Compra", "Estado Entrada", "Total Pagado"],
            ["ENT-1", "EVE-1", "2026-01-05", "Validada", "=40*2"],
        ],
        "Asistentes": [["ID Asistente", "Nombre"], ["ASI-1", "Pedro"]],
        "Recintos": [["ID Recinto", "Nombre Recinto"], ["REC-1", "Teatro"]],
    },
    "fitness": {
        "Gimnasios": [["ID Gimnasio", "Nombre"], ["GYM-1", "Gym Centro"]],
        "Membresias": [
            ["ID Membresia", "Fecha Inicio", "Estado Membresia", "Cuota Pagada"],
            ["MEM-1", "2026-02-05", "Vigente", "=35*2"],
        ],
        "Entrenadores": [["ID Entrenador", "Nombre"], ["ENT-1", "Ana"]],
        "Clases_Fitness": [
            ["ID Clase", "Fecha Clase", "Estado", "Cupo"],
            ["CLA-1", "2026-02-07", "Programada", 20],
        ],
    },
}
PRIMARY_ROLES = {
    "insurance": "policies",
    "pharmacy": "dispensations",
    "saas": "subscriptions",
    "events": "events",
    "fitness": "memberships",
}


def load_data(tables):
    book = Workbook()
    book.remove(book.active)
    for name, rows in tables.items():
        sheet = book.create_sheet(name)
        for row in rows:
            sheet.append(row)
    raw = io.BytesIO()
    book.save(raw)
    raw.seek(0)
    return asyncio.run(activate_excel_upload(
        UploadFile(filename="sector_demo.xlsx", file=raw)))


class SectorExcelIntegrationTests(unittest.TestCase):
    def test_all_five_sectors_use_real_computed_values(self):
        for domain, sheets in FIXTURES.items():
            with self.subTest(domain=domain):
                info = load_data(sheets)
                detected = inspect_business_domains()
                self.assertEqual(domain, detected["primary_domain"], detected)
                semantic = inspect_semantic_model()["semantic_model"]
                self.assertEqual(domain, semantic["domain"])
                self.assertIn(PRIMARY_ROLES[domain], semantic["entities"], semantic)
                self.assertEqual(1, info["formula_diagnostics"]["formulas_calculated"])
                dashboard = get_adaptive_dashboard_summary()
                self.assertEqual(domain, dashboard["domain"])
                self.assertTrue(any(
                    metric["role"] == PRIMARY_ROLES[domain] and metric["value"] == 1
                    for metric in dashboard["kpis"]
                ), dashboard)
                self.assertTrue(dashboard["trend"]["available"], dashboard)
                self.assertTrue(dashboard["status_distribution"]["available"], dashboard)
                self.assertTrue(dashboard["value_metrics"], dashboard)

    def test_commerce_with_cart_returns_and_orders_not_inventing_sales(self):
        load_data({
            "Pedidos": [
                ["ID Pedido", "Fecha Pedido", "Estado Pedido", "Total Pedido"],
                ["PED-1", "2026-02-05", "Pagado", 120],
            ],
            "Carritos": [
                ["ID Carrito", "Fecha Creacion", "Estado Carrito", "Total Carrito"],
                ["CAR-1", "2026-02-04", "Abierto", 120],
            ],
            "Devoluciones": [
                ["ID Devolucion", "Fecha Devolucion", "Estado Devolucion", "Monto Reembolsado"],
                ["DEV-1", "2026-02-06", "Completada", 20],
            ],
            "Productos": [["ID Producto", "Nombre", "Precio"], ["PRO-1", "Cuaderno", 15]],
        })
        detected = inspect_business_domains()
        self.assertEqual("retail", detected["primary_domain"], detected)
        semantic = inspect_semantic_model()["semantic_model"]
        self.assertTrue({"orders", "carts", "returns"}.issubset(semantic["entities"]), semantic)
        self.assertNotIn("sales", semantic["entities"])
        metrics = get_adaptive_dashboard_summary()["value_metrics"]
        self.assertEqual(20, next(m["value"] for m in metrics
                                  if m["role"] == "returns" and m["field"] == "amount"))

    def test_banking_and_supply_chain_extensions(self):
        load_data({
            "Cuentas": [["ID Cuenta", "Nombre"], ["CT-1", "Cuenta A"]],
            "Transacciones": [
                ["ID Transaccion", "Fecha", "Monto"],
                ["TX-1", "2026-02-03", 40],
            ],
            "Prestamos": [
                ["ID Prestamo", "Fecha Desembolso", "Monto Desembolsado", "Estado Prestamo"],
                ["PR-1", "2026-02-04", 5000, "Activo"],
            ],
            "Tarjetas_Bancarias": [
                ["ID Tarjeta", "Estado Tarjeta"], ["TAR-1", "Activa"]
            ],
            "Sucursales_Bancarias": [
                ["ID Sucursal", "Nombre"], ["SUC-1", "Centro"]
            ],
        })
        self.assertEqual("finance_accounting", inspect_business_domains()["primary_domain"])
        semantic = inspect_semantic_model()["semantic_model"]
        self.assertIn("loans", semantic["entities"])
        self.assertIn("cards", semantic["entities"])
        self.assertIn("branches", semantic["entities"])
        load_data({
            "Envios": [
                ["ID Envio", "Fecha Envio", "Estado Envio"],
                ["ENV-1", "2026-02-03", "Entregado"],
            ],
            "Movimientos_Inventario": [
                ["ID Movimiento", "Fecha Movimiento", "Cantidad"],
                ["MOV-1", "2026-02-03", 10],
            ],
            "Ordenes_Compra": [
                ["ID Orden Compra", "Fecha Orden", "Total Compra", "Estado Orden"],
                ["OC-1", "2026-02-01", 250, "Recibida"],
            ],
            "Transferencias_Almacen": [
                ["ID Transferencia", "Fecha Transferencia", "Cantidad"],
                ["TR-1", "2026-02-02", 4],
            ],
        })
        self.assertEqual("logistics", inspect_business_domains()["primary_domain"])
        semantic = inspect_semantic_model()["semantic_model"]
        self.assertTrue({"shipments", "stock_movements", "purchase_orders", "transfers"}
                        .issubset(semantic["entities"]), semantic)


if __name__ == "__main__":
    unittest.main()

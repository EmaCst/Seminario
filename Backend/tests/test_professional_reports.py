"""Phase-2 reporting regression tests: sources, date scope, verified graphs and PDF.

Run: python -m unittest discover -s tests -p 'test_professional_reports.py' -v
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine, text

from app.analysis.adaptive_analytics_service import _trend_analysis
from app.reports import report_configuration as report
from app.reports.configured_pdf import render_report_snapshot


def series(start_year=2024, count=24, base=100):
    return [
        {"year": start_year + index // 12, "month": index % 12 + 1,
         "total": base + index * 2}
        for index in range(count)
    ]


def fixture(domain):
    raw = series()
    return (
        {
            "database": "empresa_demo", "provider": "excel", "domain": domain,
            "kpis": [{"role": "appointments" if domain == "healthcare" else "enrollments",
                      "value": 555, "table": "records"}],
        },
        {
            "trend": _trend_analysis({"available": True, "role":
                                      "appointments" if domain == "healthcare" else "enrollments",
                                      "data": raw}),
            "rankings": [{"title": "Ranking global - no filtrar", "data": [{"label": "A", "value": 50}]}],
            "distributions": [{"label": "Estado", "data": [{"label": "A", "total": 50}]}],
            "numeric_metrics": [{"role": "appointments", "total": 1000}],
            "insights": [{"text": "Este dato es global"}],
        },
    )


class ReportConfigurationTests(unittest.TestCase):
    def test_validates_months_and_sections(self):
        with self.assertRaises(ValidationError):
            report.ReportConfiguration(start_month="2025-01")
        with self.assertRaises(ValidationError):
            report.ReportConfiguration(start_month="2025-12", end_month="2025-01")
        with self.assertRaises(ValidationError):
            report.ReportConfiguration(start_month="2020-01", end_month="2031-01")
        with self.assertRaises(ValidationError):
            report.ReportConfiguration(sections=[])
        with self.assertRaises(ValidationError):
            report.ReportConfiguration(sections=["executive", "executive"])
        with self.assertRaises(ValidationError):
            report.ReportConfiguration(
                visualization_ids=["one"], sections=["executive"],
            )
        config = report.ReportConfiguration(
            report_type="custom", sections=["visualizations", "methodology"],
            visualization_ids=["one"], start_month="2025-01", end_month="2025-03",
        )
        self.assertEqual(("2025-01-01", "2025-04-01"), config.period_bounds)

    def test_source_changed_rejects_cross_database_report(self):
        with patch.object(report, "get_report_options", return_value={
            "source": {"key": "excel:demo", "database": "demo", "provider": "excel"},
        }):
            with self.assertRaisesRegex(ValueError, "fuente activa cambió"):
                report._active_source(report.ReportConfiguration(source_key="postgresql:otra"))

    def test_two_business_domains_scope_real_monthly_values(self):
        for domain in ("healthcare", "education"):
            with self.subTest(domain=domain):
                dashboard, analytics = fixture(domain)
                config = report.ReportConfiguration(
                    start_month="2025-01", end_month="2025-03",
                    sections=["executive", "analytics", "methodology"],
                )
                with patch.object(report, "get_adaptive_dashboard_summary", return_value=dashboard):
                    with patch.object(report, "get_adaptive_analytics", return_value=analytics):
                        with patch.object(report, "_monthly_kpis", return_value=(
                            [{"role": dashboard["kpis"][0]["role"],
                              "value": 3, "table": "records", "period_filtered": True}], [])):
                            with patch.object(report, "_active_source", return_value={
                                "database": "empresa_demo", "provider": "excel",
                                "key": "excel:empresa_demo",
                            }):
                                snapshot = report.prepare_report(config)
                scoped = snapshot["analytics"]
                self.assertEqual(3, scoped["trend"]["periods"])
                self.assertEqual("03/2025", scoped["trend"]["current"]["period"])
                self.assertEqual(3, snapshot["dashboard"]["kpis"][0]["value"])
                for key in ("rankings", "distributions", "numeric_metrics", "insights"):
                    self.assertEqual([], scoped[key], key)
                self.assertTrue(any("se omiten" in warning for warning in snapshot["warnings"]))

    def test_monthly_kpi_counts_only_rows_inside_period(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE citas (fecha TEXT, estado TEXT)"))
                for value in ("2024-12-31", "2025-01-01", "2025-02-05", "2025-03-31",
                              "2025-04-01"):
                    connection.execute(text(
                        "INSERT INTO citas (fecha, estado) VALUES (:fecha, 'completado')"
                    ), {"fecha": value})
            with patch.object(report, "inspect_semantic_model", return_value={
                "semantic_model": {
                    "entities": {"appointments": {"table": "citas",
                                                 "columns": {"date": "fecha"}}},
                },
            }):
                with patch.object(report, "get_connection", side_effect=engine.connect):
                    with patch.object(report, "_quote", side_effect=lambda name: f'"{name}"'):
                        kpis, omitted = report._monthly_kpis({
                            "kpis": [{"role": "appointments", "table": "citas", "value": 5}],
                        }, "2025-01-01", "2025-04-01")
            self.assertEqual(3, kpis[0]["value"])
            self.assertEqual([], omitted)
        finally:
            engine.dispose()

    def test_saved_visualization_is_rejected_for_other_source(self):
        config = report.ReportConfiguration(
            sections=["visualizations"], visualization_ids=["not-mine"],
        )
        with patch.object(report, "list_saved_visualizations", return_value=[]):
            with self.assertRaisesRegex(ValueError, "fuente activa"):
                report._selected_visualizations(config, [])

    def test_saved_chart_uses_calendar_filters_without_mutating_original(self):
        from app.visualizations.visualization_service import VisualizationDefinition
        definition = VisualizationDefinition(
            title="Citas por estado", visualization="bar", table="citas",
            group_by="estado",
        )
        schema = SimpleNamespace(tables={
            "citas": SimpleNamespace(columns=[
                SimpleNamespace(name="fecha", type="DATE"),
                SimpleNamespace(name="estado", type="VARCHAR"),
            ]),
        })
        config = report.ReportConfiguration(start_month="2025-01", end_month="2025-12")
        with patch.object(report, "inspect_database", return_value=schema):
            scoped = report._period_visualization(definition, config)
        self.assertEqual(0, len(definition.filters))
        self.assertEqual(2, len(scoped.filters))
        self.assertEqual(("gte", "2025-01-01"), (scoped.filters[0].operator, scoped.filters[0].value))
        self.assertEqual(("lt", "2026-01-01"), (scoped.filters[1].operator, scoped.filters[1].value))


class ReportPdfTests(unittest.TestCase):
    def _snapshot(self):
        config = report.ReportConfiguration(
            report_type="custom", title="Reporte de clínica",
            sections=["executive", "visualizations", "methodology"],
            start_month="2025-01", end_month="2025-02",
            visualization_ids=["demo"],
        )
        dashboard, analytics = fixture("healthcare")
        analytics["trend"] = _trend_analysis({
            "available": True, "role": "appointments",
            "data": series()[-12:-10],
        })
        analytics["insights"] = []
        analytics["rankings"] = []
        return {
            "configuration": config.model_dump(),
            "source": {"key": "excel:clinica", "database": "clinica", "provider": "excel"},
            "generated_at": "2026-10-19T22:00:00+00:00",
            "period": {"from": "2025-01", "to": "2025-02"},
            "sections": config.enabled_sections,
            "warnings": ["Ranking global omitido por falta de filtro verificable."],
            "dashboard": {**dashboard, "kpis": [{"role": "appointments", "value": 21}]},
            "analytics": analytics,
            "forecast": None, "anomalies": None,
            "visualizations": [
                {"id": "demo", "title": "Citas por estado", "type": "bar",
                 "data": [{"dimension": "Atendidas", "value": 15},
                          {"dimension": "Canceladas", "value": 6}],
                 "definition": {"table": "citas", "group_by": "estado",
                                "aggregation": "count", "filters": []}},
            ],
        }

    def test_pdf_with_cover_sections_and_verified_chart(self):
        data, filename = render_report_snapshot(self._snapshot())
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertGreater(len(data), 3500)
        self.assertTrue(filename.endswith(".pdf"))
        self.assertIn("clinica", filename)

    def test_pdf_handles_empty_visualization_list_without_crashing(self):
        snapshot = self._snapshot()
        snapshot["visualizations"] = []
        data, _ = render_report_snapshot(snapshot)
        self.assertTrue(data.startswith(b"%PDF-"))

    def test_pdf_forecast_with_real_out_of_sample_metadata_and_anomalies(self):
        from app.ml.seasonal_forecasting import forecast_monthly
        snapshot = self._snapshot()
        snapshot["configuration"]["sections"] = ["predictive", "methodology"]
        snapshot["sections"] = ["predictive", "methodology"]
        snapshot["configuration"]["visualization_ids"] = []
        snapshot["visualizations"] = []
        points = series(start_year=2023, count=36)
        predicted = forecast_monthly(points, 3)
        snapshot["forecast"] = {**predicted, "training_points": points}
        snapshot["anomalies"] = {"anomalies": [{
            "year": 2025, "month": 11, "total": 19, "expected_total": 120,
            "deviation": -101, "severity": "alta", "pct_vs_expected": -84.17,
            "explanation": "Noviembre fue inferior a la referencia histórica.",
            "diagnostic_explanation": "No se ha demostrado una causa.",
        }]}
        data, name = render_report_snapshot(snapshot)
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertGreater(len(data), 3000)
        self.assertIn("predictive", name)

    def test_pdf_uses_sanitized_filename(self):
        snapshot = self._snapshot()
        snapshot["source"]["database"] = "clinica/con datos \\ externos"
        data, name = render_report_snapshot(snapshot)
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertNotIn("/", name)
        self.assertNotIn("\\\\", name)

    def test_pdf_predictive_section_with_insufficient_data(self):
        snapshot = self._snapshot()
        snapshot["configuration"]["sections"] = ["predictive", "methodology"]
        snapshot["sections"] = ["predictive", "methodology"]
        snapshot["configuration"]["visualization_ids"] = []
        snapshot["visualizations"] = []
        data, _ = render_report_snapshot(snapshot)
        self.assertTrue(data.startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()

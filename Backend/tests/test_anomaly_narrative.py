"""Tests for accurate, grounded, human-readable anomaly explanations."""
import unittest
from unittest.mock import patch

from app.ml.anomaly_detection import detect_anomalies
from app.ml.anomaly_narrative import narrate_monthly_anomaly
from app.ml import predictive_service as service


def sample():
    return {
        "year": 2025, "month": 11, "total": 150,
        "expected_total": 1000, "deviation": -850,
        "pct_vs_expected": -85,
        "expected_basis": "annual_calendar_median",
        "anomaly": True,
    }


class AnomalyNarrativeTests(unittest.TestCase):
    def test_display_month_year_without_inventing_event_day(self):
        narrative = narrate_monthly_anomaly(sample(), "count")
        self.assertEqual("2025-11", narrative["period_iso"])
        self.assertEqual("noviembre de 2025", narrative["period_label"])
        self.assertEqual("month", narrative["period_granularity"])
        self.assertIn("150.00 registros", narrative["explanation"])
        self.assertIn("1,000.00 registros", narrative["explanation"])
        self.assertIn("85.0%", narrative["explanation"])
        self.assertIn("otros años", narrative["explanation"])
        self.assertNotIn("1 de noviembre", narrative["explanation"])

    def test_verified_categorical_and_related_context_as_evidence(self):
        investigation = {
            "reference_period": {"year": 2024, "month": 11},
            "reference_type": "same_month_previous_year",
            "contributors": [
                {"dimension": "status", "category": "cancelado",
                 "reference": 5, "current": 35, "change": 30},
            ],
            "related_indicators": [
                {"role": "appointments", "reference": 15, "current": 7, "change": -8},
            ],
        }
        narrative = narrate_monthly_anomaly(sample(), "count", investigation)
        self.assertIn("noviembre de 2024", narrative["diagnostic_explanation"])
        self.assertIn("«cancelado»", narrative["diagnostic_explanation"])
        self.assertIn("pasó de 5.00 registros a 35.00 registros",
                      narrative["diagnostic_explanation"])
        self.assertIn("citas", narrative["diagnostic_explanation"])
        self.assertIn("no demuestran la causa", narrative["diagnostic_explanation"])
        self.assertIn("Conviene revisar", narrative["recommendation"])

    def test_without_context_does_not_invent_root_cause(self):
        narrative = narrate_monthly_anomaly(sample(), "amount")
        self.assertIn("un importe total de 150.00", narrative["explanation"])
        self.assertIn("No se identificaron desgloses", narrative["diagnostic_explanation"])
        self.assertIn("sin más datos", narrative["diagnostic_explanation"])

    def test_zero_expected_value_does_not_divide_by_zero(self):
        point = dict(sample(), expected_total=0, deviation=150, pct_vs_expected=None)
        narrative = narrate_monthly_anomaly(point, "quantity")
        self.assertIn("150.00 unidades", narrative["explanation"])
        self.assertNotIn("None%", narrative["explanation"])

    def test_short_history_has_explicit_seasonality_limit(self):
        point = dict(sample(), expected_basis="robust_trend")
        narrative = narrate_monthly_anomaly(point, "average")
        self.assertIn("un promedio de 150.00", narrative["explanation"])
        self.assertIn("no se ha verificado un patrón anual", narrative["explanation"])

    def test_detection_with_zero_baseline_still_explains_anomaly(self):
        points = [
            {"year": 2023 + index // 12, "month": index % 12 + 1,
             "total": 200 if index == 25 else 0}
            for index in range(36)
        ]
        result = detect_anomalies(points)
        peak = [item for item in result["anomalies"]
                if item["year"] == 2025 and item["month"] == 2]
        self.assertEqual(1, len(peak))
        self.assertIsNone(peak[0]["pct_vs_expected"])
        self.assertIn("referencia es cero", peak[0]["reason"])

    def test_api_preserves_statistics_and_attaches_narrative(self):
        points = [
            {"year": 2022 + index // 12, "month": index % 12 + 1,
             "total": 200 if index == 25 else 1000}
            for index in range(48)
        ]
        candidate = service.TimeSeriesCandidate(
            role="appointments", table="citas", date_column="fecha",
            data=points, domain="healthcare",
            entity={"table": "citas", "columns": {"date": "fecha"}, "ambiguous": False},
        )
        with patch.object(service, "_find_best_time_series", return_value=candidate):
            with patch.object(service, "inspect_semantic_model",
                              return_value={"semantic_model": {"entities": {}}}):
                result = service.detect_monthly_anomalies("citas")
        self.assertTrue(result["anomalies"])
        first = result["anomalies"][0]
        self.assertEqual("month", first["period_granularity"])
        self.assertIn("explic", first["diagnostic_explanation"].lower())
        self.assertIn("expected_total", first)
        self.assertIn("anomaly_score", first)
        self.assertIn("recommendation", first)


if __name__ == "__main__":
    unittest.main()

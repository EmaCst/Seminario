"""Deterministic regression tests for cross-domain temporal ML.

Run with: python -m unittest tests.test_robust_ml
No Ollama, live database, or external service required.
"""
import unittest
from unittest.mock import patch

from app.ml.anomaly_detection import detect_anomalies
from app.ml.diagnostic_service import explain_deviations
from app.ml.seasonal_forecasting import forecast_monthly
from app.ml import predictive_service as service


def synthetic(years=4, seasonal=True):
    result = []
    for index in range(years * 12):
        month = index % 12 + 1
        total = 1000 + 4 * index
        if seasonal:
            total += 500 if month in (11, 12) else -220 if month == 2 else 0
        result.append({"year": 2022 + index // 12, "month": month, "total": total})
    return result


class RobustForecastTests(unittest.TestCase):
    def test_seasonality_repeats_in_out_of_sample_forecast(self):
        result = forecast_monthly(synthetic(), 12)
        self.assertIn(result["model"], {"seasonal_trend", "seasonal_naive"})
        self.assertGreater(result["forecast"][10]["predicted_total"],
                           result["forecast"][9]["predicted_total"])
        self.assertTrue(result["seasonality_evaluated"])
        self.assertTrue(any(item["month"] == 11 for item in result["seasonal_patterns"]))

    def test_trend_only_prefers_simple_model(self):
        result = forecast_monthly(synthetic(seasonal=False), 3)
        self.assertEqual("linear_regression", result["model"])
        self.assertEqual([], result["seasonal_patterns"])

    def test_horizon_is_included_in_rolling_backtest(self):
        short = forecast_monthly(synthetic(), 1)
        long = forecast_monthly(synthetic(), 12)
        self.assertEqual(1, short["validation"]["horizon"])
        self.assertEqual(12, long["validation"]["horizon"])
        self.assertGreater(long["validation"]["samples"], short["validation"]["samples"])
        self.assertIn("naive_last", long["validation"]["candidates"])
        self.assertIn("seasonal_trend", long["validation"]["candidates"])
        self.assertIsNotNone(long["validation"]["selected"]["mae"])
        self.assertIsNotNone(long["validation"]["selected"]["rmse"])

    def test_insufficient_history_is_explicit(self):
        result = forecast_monthly(synthetic()[:5], 3)
        self.assertFalse(result["seasonality_evaluated"])
        self.assertEqual("insufficient", result["confidence"])
        self.assertIsNone(result["forecast"][0]["lower_estimate"])

    def test_gaps_do_not_imply_zero_month(self):
        points = synthetic()
        points.pop(4)
        result = forecast_monthly(points, 3)
        self.assertFalse(result["seasonality_evaluated"])
        self.assertEqual(1, result["data_quality"]["missing_months"])
        self.assertIn("sin registros", result["warning"])

    def test_duplicates_and_unsorted_data_rejected(self):
        points = synthetic()
        points[2] = dict(points[1])
        with self.assertRaisesRegex(ValueError, "repetirse"):
            forecast_monthly(points, 3)

    def test_reject_invalid_horizon(self):
        with self.assertRaises(ValueError):
            forecast_monthly(synthetic(), 13)


class ContextualAnomalyTests(unittest.TestCase):
    def test_recurring_holiday_peaks_not_anomalous(self):
        result = detect_anomalies(synthetic())
        self.assertTrue(result["baseline"]["annual_pattern_evaluated"])
        self.assertEqual([], result["anomalies"])
        self.assertIn(11, [p["month"] for p in result["seasonal_patterns"]])

    def test_year_three_collapse_is_flagged(self):
        points = synthetic()
        points[2 * 12 + 10]["total"] = 150
        result = detect_anomalies(points)
        matching = [p for p in result["anomalies"]
                    if p["year"] == 2024 and p["month"] == 11]
        self.assertEqual(1, len(matching))
        self.assertEqual("drop", matching[0]["direction"])
        self.assertGreater(matching[0]["expected_total"], matching[0]["total"])
        self.assertIn("estacional", result["warning"].lower())

    def test_nonconsecutive_series_warns(self):
        points = synthetic()
        points.pop(8)
        result = detect_anomalies(points)
        self.assertFalse(result["baseline"]["annual_pattern_evaluated"])
        self.assertEqual(1, result["data_quality"]["missing_months"])

    def test_diagnostics_without_verified_dimensions_never_hallucinates(self):
        point = {"year": 2025, "month": 11, "deviation": -500}
        result = explain_deviations([point], synthetic(), domain="education",
                                    role="enrollments", entity={"columns": {"date": "fecha"}},
                                    metric="count")
        self.assertEqual([], result["investigations"][0]["contributors"])
        self.assertEqual("not_established",
                         result["investigations"][0]["causality"])

    def test_domain_routing_retained_with_new_anomaly_engine(self):
        fake = service.TimeSeriesCandidate(
            role="appointments", table="citas", date_column="fecha",
            data=synthetic(), domain="healthcare", entity={"columns": {"date": "fecha"}},
        )
        with patch.object(service, "_find_best_time_series", return_value=fake):
            result = service.detect_monthly_anomalies("citas")
        self.assertEqual("appointments", result["role"])
        self.assertIn("diagnostics", result)
        self.assertIn("series", result)
        self.assertIn("baseline", result)


if __name__ == "__main__":
    unittest.main()

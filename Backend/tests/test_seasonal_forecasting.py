import unittest

from app.ml.seasonal_forecasting import forecast_monthly


def series(months=36, seasonal=True):
    data = []
    for index in range(months):
        month = index % 12 + 1
        year = 2023 + index // 12
        seasonal_effect = (-250 if month == 2 else 300 if month in (11, 12) else 0) if seasonal else 0
        data.append({"year": year, "month": month, "total": 1000 + index * 3 + seasonal_effect})
    return data


class SeasonalForecastTests(unittest.TestCase):
    def test_repeating_february_dip_and_holiday_peak(self):
        result = forecast_monthly(series(), 12)
        self.assertIn(result["model"], {"seasonal_trend", "seasonal_naive"})
        self.assertGreater(result["forecast"][10]["predicted_total"], result["forecast"][9]["predicted_total"])
        self.assertLess(result["forecast"][1]["predicted_total"], result["forecast"][0]["predicted_total"])
        self.assertIn(2, [p["month"] for p in result["seasonal_patterns"] if p["direction"] == "decrease"])
        self.assertIn(11, [p["month"] for p in result["seasonal_patterns"] if p["direction"] == "increase"])

    def test_trend_only_is_not_forced_into_seasonality(self):
        result = forecast_monthly(series(seasonal=False), 12)
        self.assertEqual("linear_regression", result["model"])
        self.assertEqual([], result["seasonal_patterns"])

    def test_short_history_has_no_unverified_seasonal_patterns(self):
        result = forecast_monthly(series(12), 3)
        self.assertIn(result["model"], {"linear_regression", "naive_last"})
        self.assertFalse(result["seasonality_evaluated"])

    def test_gapped_months_disable_seasonal_model(self):
        points = series()
        points.pop(5)
        result = forecast_monthly(points, 3)
        self.assertEqual("linear_regression", result["model"])
        self.assertFalse(result["seasonality_evaluated"])

    def test_backtest_and_uncertainty_available(self):
        result = forecast_monthly(series(), 3)
        self.assertGreater(result["validation"]["months"], 0)
        self.assertIsNotNone(result["validation"]["selected"]["mae"])
        self.assertGreaterEqual(result["forecast"][0]["lower_estimate"], 0)
        self.assertGreaterEqual(result["forecast"][0]["upper_estimate"], result["forecast"][0]["predicted_total"])


if __name__ == "__main__":
    unittest.main()

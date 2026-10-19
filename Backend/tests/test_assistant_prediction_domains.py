"""Predictions must target requested entities/metrics, not longest random series."""
import unittest
from unittest.mock import patch

from app.ml import predictive_service as prediction


def _data(n):
    return [{"year": 2026, "month": i, "total": i * 10} for i in range(1, n + 1)]


def _model(domain, entities):
    return {"semantic_model": {
        "domain": domain, "ambiguous_domain": False, "entities": entities,
    }}


def _entity(table, *, amount=False):
    columns = {"date": "fecha"}
    if amount:
        columns["amount"] = "monto"
    return {"table": table, "columns": columns, "ambiguous": False}


class PredictionRoutingTests(unittest.TestCase):
    def test_requested_role_beats_longer_unrelated_series(self):
        semantic = _model("education", {
            "enrollments": _entity("inscripciones"),
            "attendance": _entity("asistencia"),
        })
        def series(table, _date):
            return _data(4) if table == "inscripciones" else _data(12)

        with patch.object(prediction, "inspect_semantic_model", return_value=semantic):
            with patch.object(prediction, "_monthly_count", side_effect=series):
                selected = prediction._find_best_time_series(
                    "pronostica inscripciones", minimum_points=3)
        self.assertEqual("enrollments", selected.role)
        self.assertEqual(4, len(selected.data))
        self.assertEqual("count", selected.metric)

    def test_requested_money_uses_amount_not_count(self):
        semantic = _model("retail", {
            "payments": _entity("pagos", amount=True),
        })
        with patch.object(prediction, "inspect_semantic_model", return_value=semantic):
            with patch.object(prediction, "_monthly_count",
                              side_effect=AssertionError("Do not count payments")):
                with patch.object(prediction, "_query_series", return_value=_data(5)):
                    with patch.object(prediction, "_measure", return_value="SUM(t.monto)"):
                        chosen = prediction._find_best_time_series(
                            "pronostica el monto de pagos", minimum_points=3)
        self.assertEqual("amount", chosen.metric)
        self.assertEqual("payments", chosen.role)

    def test_missing_requested_role_does_not_use_another_series(self):
        semantic = _model("education", {"enrollments": _entity("inscripciones")})
        with patch.object(prediction, "inspect_semantic_model", return_value=semantic):
            with self.assertRaisesRegex(ValueError, "No encontré"):
                prediction._find_best_time_series("pronostica estudiantes")

    def test_other_domain_entity_is_not_implicitly_selected(self):
        semantic = _model("human_resources", {"attendance": _entity("asistencia")})
        with patch.object(prediction, "inspect_semantic_model", return_value=semantic):
            with self.assertRaisesRegex(ValueError, "entidad solicitada"):
                prediction._find_best_time_series("predice las citas")

    def test_insufficient_months_reports_requested_role(self):
        semantic = _model("transportation", {"trips": _entity("viajes")})
        with patch.object(prediction, "inspect_semantic_model", return_value=semantic):
            with patch.object(prediction, "_monthly_count", return_value=_data(2)):
                with self.assertRaisesRegex(ValueError, "3 meses"):
                    prediction._find_best_time_series(
                        "pronostica viajes", minimum_points=3)

    def test_ambiguous_domain_blocks_forecast(self):
        semantic = _model("healthcare", {"appointments": _entity("citas")})
        semantic["semantic_model"]["ambiguous_domain"] = True
        with patch.object(prediction, "inspect_semantic_model", return_value=semantic):
            with self.assertRaisesRegex(ValueError, "ambiguo"):
                prediction._find_best_time_series("pronostica citas")

    def test_forecast_exposes_metric(self):
        semantic = _model("education", {"enrollments": _entity("inscripciones")})
        with patch.object(prediction, "inspect_semantic_model", return_value=semantic):
            with patch.object(prediction, "_monthly_count", return_value=_data(6)):
                result = prediction.forecast_next_months(
                    horizon=2, question="pronostica inscripciones")
        self.assertEqual("count", result["metric"])
        self.assertEqual("enrollments", result["role"])
        self.assertEqual(2, len(result["forecast"]))


if __name__ == "__main__":
    unittest.main()

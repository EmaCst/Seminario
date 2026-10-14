import unittest
from unittest.mock import patch

from app.services.assistant_service import (
    _attribution_followup,
    _compare_months,
    _conversation_reply,
)


class AssistantIntentTests(unittest.TestCase):
    def test_greeting_does_not_require_database(self):
        self.assertIn("Hola", _conversation_reply("hola"))
        self.assertIsNone(_conversation_reply("hola, dime las ventas"))

    def test_product_attribution_retains_context(self):
        history = [{"role": "user", "content": "dime la diferencia entre junio y febrero"}]
        question = _attribution_followup("¿qué producto marcó esa diferencia?", history)
        self.assertIn("junio", question)
        self.assertIn("febrero", question)
        self.assertIn("producto", question)

    def test_month_comparison_from_history(self):
        history = [{"role": "user", "content": "diferencia de ventas entre junio y febrero"}]
        data = {"available": True, "data": [
            {"year": 2026, "month": 6, "total": 8660.64},
            {"year": 2026, "month": 2, "total": 3057.60},
        ]}
        with patch("app.analysis.dashboard_service.get_sales_by_month", return_value=data):
            result = _compare_months("¿y cuál fue la diferencia entre los dos meses?", history)
        self.assertIn("5,603.04", result["answer"])


if __name__ == "__main__":
    unittest.main()

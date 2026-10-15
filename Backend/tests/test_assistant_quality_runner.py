"""Regression tests for structured reports and isolated synthetic quality runs."""
import io
import os
import unittest
from unittest.mock import patch

from app.database.database_manager import DatabaseManager
from app.quality.fixtures import DOMAINS, connected_fixture
from app.quality.run import RecordingResult, _markdown_report


class QualityRunnerTests(unittest.TestCase):
    def test_report_marks_unrun_external_integrations_explicitly(self):
        report = {
            "created_at": "2026-01-01T00:00:00+00:00",
            "status": "PASS",
            "summary": {"tests": 1, "passed": 1, "failed": 0,
                        "errors": 0, "skipped": 0},
            "duration_ms": 10.0,
            "ollama": {"status": "not_run"},
            "tests": [{"test": "sample", "status": "passed"}],
        }
        text = _markdown_report(report)
        self.assertIn("SQL Server/PostgreSQL reales: **no ejecutados**", text)
        self.assertIn("Gemma/Ollama local: **not_run**", text)
        self.assertIn("PASS", text)

    def test_failing_subtest_is_recorded_not_hidden(self):
        class DeliberateFailure(unittest.TestCase):
            def runTest(self):
                with self.subTest(example="synthetic"):
                    self.assertEqual(1, 2)
        stream = io.StringIO()
        suite = unittest.TestSuite([DeliberateFailure()])
        result = unittest.TextTestRunner(
            stream=stream, resultclass=RecordingResult, verbosity=0).run(suite)
        self.assertFalse(result.wasSuccessful())
        self.assertTrue(any(item["status"] == "failed"
                            for item in result.records), result.records)

    def test_quality_flag_disables_env_auto_connection(self):
        with patch.dict(os.environ, {
            "KENNETH_QUALITY_MODE": "1",
            "DB_SERVER": "hypothetical.host.invalid",
            "DB_DATABASE": "must_not_connect",
        }):
            with patch.object(DatabaseManager, "configure",
                              side_effect=AssertionError("External connection attempted")):
                manager = DatabaseManager()
        self.assertFalse(manager.status()["connected"])

    def test_fixture_restores_original_database_manager(self):
        from app.database.database_manager import database_manager
        original_status = database_manager.status()
        fixture = DOMAINS[0]
        with connected_fixture(fixture):
            self.assertEqual("excel", database_manager.status()["provider"])
            self.assertEqual("retail", fixture.domain)
        self.assertEqual(original_status, database_manager.status())


if __name__ == "__main__":
    unittest.main()

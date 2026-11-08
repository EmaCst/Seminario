import unittest
from unittest.mock import patch

from app.database.source_cache import source_cached


class SourceCacheTests(unittest.TestCase):
    def test_reuses_per_revision_and_returns_independent_values(self):
        active = {"revision": "excel-1"}
        calls = []

        @source_cached(seconds=120)
        def load():
            calls.append(active["revision"])
            return {"tables": ["customers"]}

        with patch("app.database.source_cache.database_manager.status",
                   side_effect=lambda: dict(active)):
            first = load()
            first["tables"].append("polluted")
            self.assertEqual(load(), {"tables": ["customers"]})
            self.assertEqual(calls, ["excel-1"])
            active["revision"] = "sql-2"
            self.assertEqual(load(), {"tables": ["customers"]})
            self.assertEqual(calls, ["excel-1", "sql-2"])

    def test_no_revision_and_errors_are_not_cached(self):
        calls = []

        @source_cached(seconds=120)
        def load():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("temporary problem")
            return len(calls)

        with patch("app.database.source_cache.database_manager.status",
                   return_value={"revision": "source-a"}):
            with self.assertRaises(RuntimeError):
                load()
            self.assertEqual(load(), 2)
            self.assertEqual(load(), 2)
        self.assertEqual(len(calls), 2)

        with patch("app.database.source_cache.database_manager.status",
                   return_value={"revision": None}):
            self.assertEqual(load(), 3)
            self.assertEqual(load(), 4)

    def test_source_switch_during_build_never_populates_cache(self):
        active = {"revision": "before"}
        calls = []

        @source_cached(seconds=120)
        def load():
            calls.append(active["revision"])
            active["revision"] = "after"
            return calls[-1]

        with patch("app.database.source_cache.database_manager.status",
                   side_effect=lambda: dict(active)):
            self.assertEqual(load(), "before")
            self.assertEqual(load(), "after")
            self.assertEqual(calls, ["before", "after"])


if __name__ == "__main__":
    unittest.main()

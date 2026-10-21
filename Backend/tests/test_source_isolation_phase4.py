"""Phase 4: source generations, API guards, physical identity and saved views."""
import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.database.database_manager import DatabaseManager
from app.database.source_guard import source_revision_middleware
from app.visualizations import visualization_store as store


class SourceGenerationTests(unittest.TestCase):
    def make_manager(self):
        with patch.dict(os.environ, {"KENNETH_QUALITY_MODE": "1"}):
            return DatabaseManager()

    def test_same_database_reactivation_rotates_revision_but_not_identity(self):
        manager = self.make_manager()
        self.addCleanup(lambda: manager.get_engine().dispose())
        configs = dict(provider="sqlserver", server="localhost", database="Ventas",
                       username="reader")
        first = manager._activate(create_engine("sqlite+pysqlite:///:memory:"), configs)
        second = manager._activate(create_engine("sqlite+pysqlite:///:memory:"), configs)
        self.assertNotEqual(first["revision"], second["revision"])
        self.assertEqual(first["source_identity"], second["source_identity"])
        self.assertEqual(first["database"], second["database"])

    def test_same_name_different_servers_and_excel_files_are_different(self):
        manager = self.make_manager()
        one = manager._identity({"provider": "postgresql", "host": "a",
                                 "database": "ventas", "port": 5432})
        two = manager._identity({"provider": "postgresql", "host": "b",
                                 "database": "ventas", "port": 5432})
        self.assertNotEqual(one, two)
        file_a = manager._identity({"provider": "excel", "database_path": "/tmp/a/ventas.sqlite"})
        file_b = manager._identity({"provider": "excel", "database_path": "/tmp/b/ventas.sqlite"})
        self.assertNotEqual(file_a, file_b)

    def test_failed_connection_does_not_replace_previous_source(self):
        manager = self.make_manager()
        engine = create_engine("sqlite+pysqlite:///:memory:")
        manager._activate(engine, {"provider": "excel", "database": "first.xlsx",
                                   "database_path": "/tmp/first.sqlite"})
        prior = manager.status()
        with patch.object(manager, "_build_postgresql_engine",
                          side_effect=RuntimeError("connection failed")):
            with self.assertRaises(RuntimeError):
                manager.configure_postgresql("server", "second", "reader")
        self.assertEqual(prior["revision"], manager.status()["revision"])
        self.assertIs(engine, manager.get_engine())
        engine.dispose()


class SourceGuardTests(unittest.TestCase):
    @staticmethod
    def run_guard(request_headers, statuses, path="/api/dashboard/adaptive"):
        async def next_request(_request):
            return JSONResponse({"secret": "old database data"})
        request = Request({
            "type": "http", "method": "GET", "scheme": "http",
            "path": path, "raw_path": path.encode(),
            "query_string": b"", "root_path": "",
            "headers": [(k.lower().encode(), v.encode())
                        for k, v in request_headers.items()],
            "server": ("testserver", 80), "client": ("testclient", 1234),
            "http_version": "1.1",
        })
        with patch("app.database.source_guard.database_manager.status",
                   side_effect=[{"revision": v} for v in statuses]):
            return asyncio.run(source_revision_middleware(request, next_request))

    def test_old_tab_revision_rejected_before_query(self):
        response = self.run_guard(
            {"X-Kenneth-Source-Revision": "previous"},
            ["new", "new"],
        )
        self.assertEqual(409, response.status_code)
        self.assertEqual("no-store, private, max-age=0",
                         response.headers["cache-control"])

    def test_mid_request_switch_invalidates_computed_response(self):
        response = self.run_guard(
            {"X-Kenneth-Source-Revision": "old"},
            ["old", "new", "new"],
        )
        self.assertEqual(409, response.status_code)
        self.assertIn(b"SOURCE_CHANGED", response.body)
        self.assertNotIn(b"old database data", response.body)

    def test_current_revision_returns_uncached_data(self):
        response = self.run_guard(
            {"X-Kenneth-Source-Revision": "current"},
            ["current", "current", "current"],
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("current", response.headers["x-kenneth-source-revision"])
        self.assertEqual("no-store, private, max-age=0",
                         response.headers["cache-control"])


class SavedSourceIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage = patch.object(store, "STORE_FILE",
                                    Path(self.temp.name) / "views.json")
        self.storage.start()
        self.addCleanup(self.storage.stop)
        self.folder = patch.object(store, "STORE_DIR", Path(self.temp.name))
        self.folder.start()
        self.addCleanup(self.folder.stop)

    def test_saved_visualization_never_leaks_to_same_named_other_server(self):
        from app.visualizations.visualization_service import VisualizationDefinition
        from app.visualizations.visualization_store import SavedVisualizationRequest
        status = {"provider": "postgresql", "database": "ventas",
                  "source_identity": "server-one"}
        with patch.object(store.database_manager, "status", return_value=status):
            saved = store.save_visualization(SavedVisualizationRequest(
                definition=VisualizationDefinition(
                    title="Ingresos", visualization="kpi", table="ventas"
                )
            ))
            self.assertEqual(1, len(store.list_saved_visualizations()))
        with patch.object(store.database_manager, "status", return_value={
            **status, "source_identity": "server-two",
        }):
            self.assertEqual([], store.list_saved_visualizations())
            with self.assertRaisesRegex(ValueError, "fuente activa"):
                store.update_visualization_placement(
                    saved["id"], store.VisualizationPlacement(dashboard=True)
                )
        with patch.object(store.database_manager, "status", return_value=status):
            self.assertEqual([saved["id"]],
                             [v["id"] for v in store.list_saved_visualizations()])

    def test_legacy_unverified_records_do_not_auto_reappear(self):
        from app.visualizations.visualization_store import SavedVisualizationRequest
        from app.visualizations.visualization_service import VisualizationDefinition
        source = {"provider": "excel", "database": "demo.xlsx",
                  "source_identity": "actual-upload-fingerprint"}
        with patch.object(store.database_manager, "status", return_value=source):
            store.save_visualization(SavedVisualizationRequest(
                definition=VisualizationDefinition(
                    title="Demo", visualization="kpi", table="datos"
                )
            ))
        # Namespaced records remain on disk; no destructive deletion or
        # silent cross-database migration of untrusted legacy source keys.
        data = store._load()
        data["visualizations"][0]["source"] = "excel:demo.xlsx"
        store._write(data)
        with patch.object(store.database_manager, "status", return_value=source):
            self.assertEqual([], store.list_saved_visualizations())


if __name__ == "__main__":
    unittest.main()

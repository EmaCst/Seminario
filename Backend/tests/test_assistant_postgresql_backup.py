"""PostgreSQL archive import tests without requiring any live server.

The tests verify upload gating, archive preflight, safe subprocess calls,
database creation/cleanup, activation ordering and the FastAPI contract.
"""
from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from app.database import postgresql_backup_loader as pg
from app.main import app


CONFIG = {
    "provider": "postgresql",
    "host": "127.0.0.1",
    "port": 5432,
    "database": "existing_database",
    "username": "test_user",
    "password": "secret_testing_only",
    "sslmode": "prefer",
}


class PostgreSQLBackupUnitTests(unittest.TestCase):
    def test_random_name_is_safe_and_not_the_original_database(self):
        one = pg._safe_db_name("..\\recovery\\Venta 2026.backup")
        two = pg._safe_db_name("..\\recovery\\Venta 2026.backup")
        self.assertNotEqual(one, two)
        self.assertRegex(one, r"^upload_venta_2026_[a-f0-9]{12}$")
        self.assertLessEqual(len(one), 63)
        self.assertEqual('"' + one + '"', pg._quote_identifier(one))
        with self.assertRaises(ValueError):
            pg._quote_identifier("production; DROP DATABASE foo")

    def test_client_environment_does_not_inherit_other_database_credentials(self):
        with patch.dict(os.environ, {
            "PGDATABASE": "production", "PGPASSWORD": "old-password",
            "PGSERVICE": "elsewhere", "PGHOST": "example.net",
        }):
            environment = pg._client_environment(CONFIG)
        self.assertNotIn("PGDATABASE", environment)
        self.assertNotIn("PGSERVICE", environment)
        self.assertNotIn("PGHOST", environment)
        self.assertEqual("secret_testing_only", environment["PGPASSWORD"])
        self.assertEqual(os.devnull, environment["PGPASSFILE"])
        self.assertEqual("prefer", environment["PGSSLMODE"])

    def test_extension_and_magic_validation_happen_before_database_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "invalid.backup"
            archive.write_bytes(b"CREATE TABLE foo (id int);")
            with patch.object(pg, "_run_client") as runner:
                with self.assertRaisesRegex(ValueError, "Custom"):
                    pg._validate_archive(archive, ".backup", "pg_restore")
                runner.assert_not_called()

    def test_archive_list_requires_a_table(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "valid.backup"
            archive.write_bytes(b"PGDMP" + b"\x00" * 32)
            with patch.object(pg, "_run_client", return_value="4; 1259 123 VIEW public v postgres"):
                with self.assertRaisesRegex(ValueError, "tablas"):
                    pg._validate_archive(archive, ".backup", "pg_restore")
            with patch.object(pg, "_run_client", return_value="4; 1259 123 TABLE public ventas postgres") as run:
                pg._validate_archive(archive, ".backup", "pg_restore")
                command = run.call_args.args[0]
                self.assertEqual(["pg_restore", "--list", str(archive)], command)

    def test_restore_uses_no_shell_and_never_connects_to_original_target(self):
        with patch.object(pg, "_run_client", return_value="") as invoke:
            pg._restore_archive(Path("archive.backup"), "upload_ficticio_abcdef", CONFIG, "pg_restore")
        args = invoke.call_args.args[0]
        self.assertIn("--dbname", args)
        self.assertEqual("upload_ficticio_abcdef", args[args.index("--dbname") + 1])
        self.assertIn("--single-transaction", args)
        self.assertIn("--no-owner", args)
        self.assertIn("--no-privileges", args)
        self.assertIn("--no-tablespaces", args)
        self.assertIn("--no-password", args)
        self.assertIn("--no-publications", args)
        self.assertIn("--no-subscriptions", args)
        self.assertIn("--no-security-labels", args)
        self.assertNotIn("secret_testing_only", " ".join(args))
        environment = invoke.call_args.kwargs["environment"]
        self.assertEqual("secret_testing_only", environment["PGPASSWORD"])

    def test_subprocess_failure_exposes_safe_error_and_timeout(self):
        completed = Mock(returncode=1, stdout="", stderr="invalid archive")
        with patch.object(pg.subprocess, "run", return_value=completed) as runner:
            with self.assertRaisesRegex(RuntimeError, "invalid archive"):
                pg._run_client(["pg_restore", "--list", "f.backup"])
            kwargs = runner.call_args.kwargs
            self.assertEqual(subprocess.DEVNULL, kwargs["stdin"])
            self.assertTrue(kwargs["capture_output"])
            self.assertFalse(kwargs["check"])
        with patch.object(pg.subprocess, "run", side_effect=subprocess.TimeoutExpired("pg_restore", 30)):
            with self.assertRaisesRegex(RuntimeError, "tiempo"):
                pg._run_client(["pg_restore", "file"])

    def test_failure_drops_only_newly_created_database(self):
        with patch.object(pg, "_safe_db_name", return_value="upload_test_abcdef012345"):
            with patch.object(pg, "_create_database") as create:
                with patch.object(pg, "_restore_archive", side_effect=RuntimeError("broken")):
                    with patch.object(pg, "_drop_created_database") as cleanup:
                        with patch.object(pg.database_manager, "configure_postgresql") as activate:
                            with self.assertRaisesRegex(RuntimeError, "broken"):
                                pg._restore_staged(
                                    Path("test.backup"), CONFIG, "pg_restore",
                                    "test.backup", 10,
                                )
        create.assert_called_once_with("upload_test_abcdef012345", CONFIG)
        cleanup.assert_called_once_with("upload_test_abcdef012345", CONFIG)
        activate.assert_not_called()

    def test_create_failure_does_not_drop_any_database(self):
        with patch.object(pg, "_create_database", side_effect=RuntimeError("CREATE denied")):
            with patch.object(pg, "_drop_created_database") as cleanup:
                with patch.object(pg.database_manager, "configure_postgresql") as activate:
                    with self.assertRaisesRegex(RuntimeError, "CREATE denied"):
                        pg._restore_staged(
                            Path("test.backup"), CONFIG, "pg_restore", "test.backup", 10
                        )
        cleanup.assert_not_called()
        activate.assert_not_called()

    def test_success_activates_only_after_archive_and_schema_verification(self):
        sequence = []
        with patch.object(pg, "_safe_db_name", return_value="upload_test_abcdef012345"):
            with patch.object(pg, "_create_database", side_effect=lambda *_: sequence.append("create")):
                with patch.object(pg, "_restore_archive", side_effect=lambda *_: sequence.append("restore")):
                    with patch.object(pg, "_verify_restored_database",
                                      side_effect=lambda *_: sequence.append("verify") or ["ventas"]):
                        with patch.object(pg.database_manager, "configure_postgresql",
                                          side_effect=lambda **_: sequence.append("activate")) as configure:
                            with patch.object(pg, "_drop_created_database") as cleanup:
                                result = pg._restore_staged(Path("backup.backup"), CONFIG,
                                                            "pg_restore", "backup.backup", 42)
        self.assertEqual(["create", "restore", "verify", "activate"], sequence)
        cleanup.assert_not_called()
        self.assertTrue(result["restored"])
        self.assertEqual("upload_test_abcdef012345", result["database"])
        self.assertEqual(1, result["table_count"])
        self.assertEqual("upload_test_abcdef012345", configure.call_args.kwargs["database"])

    def test_validation_after_restore_failure_keeps_previous_connection(self):
        with patch.object(pg, "_create_database"):
            with patch.object(pg, "_restore_archive"):
                with patch.object(pg, "_verify_restored_database",
                                  side_effect=RuntimeError("no visible tables")):
                    with patch.object(pg, "_drop_created_database") as cleanup:
                        with patch.object(pg.database_manager, "configure_postgresql") as activate:
                            with self.assertRaisesRegex(RuntimeError, "no visible tables"):
                                pg._restore_staged(Path("a.backup"), CONFIG, "pg_restore",
                                                   "a.backup", 15)
        cleanup.assert_called_once()
        activate.assert_not_called()


class PostgreSQLBackupSettingsTests(unittest.TestCase):
    def setUp(self):
        self.original_override = pg._UPLOAD_ENABLED_OVERRIDE
        pg._UPLOAD_ENABLED_OVERRIDE = None

    def tearDown(self):
        pg._UPLOAD_ENABLED_OVERRIDE = self.original_override

    def test_runtime_checkbox_overrides_environment_without_writing_env(self):
        with patch.dict(os.environ, {"PG_BACKUP_UPLOAD_ENABLED": "0"}):
            self.assertFalse(pg.backup_upload_enabled())
            self.assertTrue(pg.set_backup_upload_enabled(True))
            self.assertTrue(pg.backup_upload_enabled())
            self.assertEqual("0", os.environ["PG_BACKUP_UPLOAD_ENABLED"])
            self.assertFalse(pg.set_backup_upload_enabled(False))
            self.assertFalse(pg.backup_upload_enabled())

    def test_cannot_change_upload_permission_during_restore(self):
        self.assertTrue(pg._RESTORE_LOCK.acquire(blocking=False))
        try:
            with self.assertRaisesRegex(ValueError, "curso"):
                pg.set_backup_upload_enabled(True)
        finally:
            pg._RESTORE_LOCK.release()

    def test_http_checkbox_local_only_and_state_reflects_backend(self):
        headers = {"Origin": "http://localhost:5173"}
        with TestClient(app) as client:
            initial = client.get("/api/database/postgresql-backup/settings")
            self.assertEqual(200, initial.status_code)
            self.assertTrue(initial.json()["manageable"])
            enabled = client.put("/api/database/postgresql-backup/settings",
                                 json={"enabled": True}, headers=headers)
            self.assertEqual(200, enabled.status_code, enabled.text)
            self.assertTrue(enabled.json()["enabled"])
            self.assertFalse(enabled.json()["persistent"])
            self.assertTrue(client.get("/api/database/postgresql-backup/settings").json()["enabled"])
            disabled = client.put("/api/database/postgresql-backup/settings",
                                  json={"enabled": False}, headers=headers)
            self.assertEqual(200, disabled.status_code)
            self.assertFalse(disabled.json()["enabled"])

    def test_http_checkbox_rejects_requests_without_trusted_local_origin(self):
        with TestClient(app) as client:
            for headers in ({}, {"Origin": "https://malicious.example"},
                            {"Origin": "http://localhost:3000"}):
                with self.subTest(headers=headers):
                    res = client.put("/api/database/postgresql-backup/settings",
                                     json={"enabled": True}, headers=headers)
                    self.assertEqual(403, res.status_code)


class PostgreSQLBackupAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_disallowed_extension_and_disabled_mode(self):
        upload = UploadFile(file=BytesIO(b"plain sql"), filename="example.sql")
        with self.assertRaisesRegex(ValueError, ".sql"):
            await pg.restore_postgresql_backup(upload)
        with patch.dict(os.environ, {"PG_BACKUP_UPLOAD_ENABLED": "0"}):
            upload = UploadFile(file=BytesIO(b"PGDMPtest"), filename="valid.backup")
            with self.assertRaisesRegex(ValueError, "deshabilitada"):
                await pg.restore_postgresql_backup(upload)

    async def test_existing_postgresql_connection_required(self):
        with patch.dict(os.environ, {"PG_BACKUP_UPLOAD_ENABLED": "1"}):
            upload = UploadFile(file=BytesIO(b"PGDMPtest"), filename="valid.backup")
            with patch.object(pg.database_manager, "get_active_config",
                              return_value={"provider": "sqlserver"}):
                with self.assertRaisesRegex(ValueError, "PostgreSQL"):
                    await pg.restore_postgresql_backup(upload)

    async def test_upload_is_cleaned_and_returns_restored_result(self):
        with patch.dict(os.environ, {"PG_BACKUP_UPLOAD_ENABLED": "1"}):
            with patch.object(pg.database_manager, "get_active_config", return_value=CONFIG):
                with patch.object(pg, "_pg_restore_executable", return_value="pg_restore"):
                    with patch.object(pg, "_validate_archive"):
                        with patch.object(pg, "_restore_staged",
                                          return_value={"restored": True, "database": "upload_example"}) as staged:
                            upload = UploadFile(
                                file=BytesIO(b"PGDMPtestdata"), filename="example.backup")
                            output = await pg.restore_postgresql_backup(upload)
        self.assertEqual("upload_example", output["database"])
        self.assertTrue(upload.file.closed)
        self.assertFalse(Path(staged.call_args.args[0]).exists())
        self.assertEqual(13, staged.call_args.args[-1])

    async def test_excessive_file_size_rejected_without_reaching_restore(self):
        # Lower the limit for the test: the fixture never writes gigabytes.
        with patch.object(pg, "MAX_BACKUP_SIZE_BYTES", 4):
            with tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / "archive"
                upload = UploadFile(file=BytesIO(b"PGDMPtoo-long"), filename="large.backup")
                with self.assertRaisesRegex(ValueError, "2 GB"):
                    await pg._save_upload(upload, destination)
        self.assertTrue(upload.file.closed)


class PostgreSQLBackupHttpTests(unittest.TestCase):
    def test_endpoint_returns_analysis_like_sqlserver(self):
        restored = {"restored": True, "database": "upload_test", "table_count": 1}
        analysis = {"database": "upload_test", "tables": ["ventas"],
                    "business_domain": {"primary": "retail"}}
        with patch("app.main.restore_postgresql_backup", new_callable=AsyncMock,
                   return_value=restored):
            with patch("app.main._current_database_analysis", return_value=analysis):
                with patch("app.main.get_adaptive_dashboard_summary",
                           return_value={"available": True}):
                    with TestClient(app) as client:
                        response = client.post(
                            "/api/database/upload/postgresql-backup",
                            files={"file": ("trusted.backup", b"PGDMPfake",
                                            "application/octet-stream")},
                        )
        self.assertEqual(200, response.status_code, response.text)
        payload = response.json()
        self.assertTrue(payload["uploaded"])
        self.assertEqual("postgresql", payload["engine"])
        self.assertEqual("upload_test", payload["database"])
        self.assertEqual("retail", payload["business_domain"]["primary"])

    def test_restore_success_is_preserved_if_semantic_inspection_fails(self):
        restored = {"restored": True, "database": "upload_test", "table_count": 1}
        with patch("app.main.restore_postgresql_backup", new_callable=AsyncMock,
                   return_value=restored):
            with patch("app.main._current_database_analysis",
                       side_effect=RuntimeError("schema unavailable")):
                with patch("app.main.get_adaptive_dashboard_summary") as dashboard:
                    with TestClient(app) as client:
                        response = client.post(
                            "/api/database/upload/postgresql-backup",
                            files={"file": ("trusted.backup", b"PGDMPfake",
                                            "application/octet-stream")},
                        )
        self.assertEqual(200, response.status_code, response.text)
        payload = response.json()
        self.assertTrue(payload["uploaded"])
        self.assertEqual("upload_test", payload["database"])
        self.assertIn("análisis", payload["analysis_warning"])
        self.assertFalse(payload["dashboard"]["available"])
        dashboard.assert_not_called()

    def test_endpoint_returns_422_for_invalid_files(self):
        with patch("app.main.restore_postgresql_backup", new_callable=AsyncMock,
                   side_effect=ValueError("formato no admitido")):
            with TestClient(app) as client:
                response = client.post(
                    "/api/database/upload/postgresql-backup",
                    files={"file": ("bad.sql", b"select 1", "text/plain")},
                )
        self.assertEqual(422, response.status_code)
        self.assertIn("formato no admitido", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()

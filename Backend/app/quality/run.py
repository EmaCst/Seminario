"""Kenneth quality gate with versioned synthetic fixtures and local reports.

Usage from Backend/
    python -m app.quality.run
    python -m app.quality.run --suite integration
    python -m app.quality.run --with-ollama

The default never connects to an external database or model; the optional
Ollama check uses a throwaway local SQLite database, not customer data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import platform
from pathlib import Path
import sys
from time import perf_counter
import traceback
import unittest

# Set before importing database_manager (which normally activates DB_SERVER from .env).
os.environ["KENNETH_QUALITY_MODE"] = "1"

from app.quality.fixtures import DOMAINS, connected_fixture


class RecordingResult(unittest.TextTestResult):
    """Per-test results without converting synthetic test data into prod claims."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records: list[dict] = []
        self._started: dict[int, float] = {}

    def startTest(self, test):
        self._started[id(test)] = perf_counter()
        super().startTest(test)

    def _record(self, test, status: str, detail: str | None = None):
        # Tests use fixed, synthetic data; exception strings are local only.
        self.records.append({
            "test": test.id(),
            "status": status,
            "elapsed_ms": round((perf_counter() - self._started.get(id(test), perf_counter())) * 1000, 2),
            **({"detail": detail[:2000]} if detail else {}),
        })

    def addSuccess(self, test):
        self._record(test, "passed")
        super().addSuccess(test)

    def addFailure(self, test, err):
        self._record(test, "failed", self._exc_info_to_string(err, test))
        super().addFailure(test, err)

    def addError(self, test, err):
        self._record(test, "error", self._exc_info_to_string(err, test))
        super().addError(test, err)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            status = "failed" if issubclass(err[0], test.failureException) else "error"
            self.records.append({
                "test": test.id(),
                "subtest": str(subtest),
                "status": status,
                "elapsed_ms": round(
                    (perf_counter() - self._started.get(id(test), perf_counter())) * 1000, 2),
                "detail": self._exc_info_to_string(err, subtest)[:2000],
            })
        super().addSubTest(test, subtest, err)

    def addSkip(self, test, reason):
        self._record(test, "skipped", reason)
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self._record(test, "expected_failure")
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self._record(test, "unexpected_success")
        super().addUnexpectedSuccess(test)


def _run_ollama_smoke() -> dict:
    """Opt-in end-to-end model test using a disposable local business fixture.

    A live model call is made, but SQL validation and query execution still use
    the same temporary SQLite fixture. Only a question and synthetic schema
    are sent to Ollama. No external/production database is activated.
    """
    from app.ai.database_context import clear_database_context_cache
    from app.services.assistant_service import ask_database

    started = perf_counter()
    fixture = next(item for item in DOMAINS if item.domain == "retail")
    clear_database_context_cache()
    question = "Lista los nombres de todos los productos registrados."
    try:
        with connected_fixture(fixture):
            response = ask_database(question)
        if response.get("mode") != "sql":
            raise AssertionError(
                f"Se esperaba consulta SQL generada por Gemma, no {response.get('mode')!r}")
        rows = response.get("data") or []
        actual_values = {str(value) for row in rows for value in row.values()}
        if not {"Café", "Pan"}.issubset(actual_values):
            raise AssertionError(
                "La consulta no devolvió ambos productos ficticios esperados.")
        answer = str(response.get("answer") or "")
        if not all(name.lower() in answer.lower() for name in ("Café", "Pan")):
            raise AssertionError(
                "La explicación de Gemma omitió uno de los productos devueltos.")
        return {"status": "passed", "question": question,
                "rows": len(rows), "mode": response["mode"],
                "elapsed_ms": round((perf_counter() - started) * 1000, 2)}
    except Exception as exc:
        return {"status": "failed", "question": question,
                "reason": f"{type(exc).__name__}: {str(exc)[:500]}",
                "elapsed_ms": round((perf_counter() - started) * 1000, 2)}
    finally:
        clear_database_context_cache()


def _markdown_report(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "# Kenneth — informe de calidad",
        "",
        f"- Fecha UTC: {report['created_at']}",
        f"- Pruebas: {summary['tests']}",
        f"- Aprobadas: {summary['passed']}",
        f"- Fallos: {summary['failed']}",
        f"- Errores: {summary['errors']}",
        f"- Omitidas: {summary['skipped']}",
        f"- Duración: {report['duration_ms']} ms",
        f"- Resultado: **{report['status']}**",
        "",
        "## Alcance comprobado",
        "",
        "- SQLite temporal: datos ficticios, introspección real, FastAPI y SQL real",
        "- Perfiles: comercio, educación, salud, transporte, hotelería, "
        "restaurantes, servicios profesionales, finanzas, manufactura y recursos humanos",
        "- SQL Server/PostgreSQL reales: **no ejecutados** (requieren un entorno desechable aparte)",
        f"- Gemma/Ollama local: **{report['ollama']['status']}**",
        "",
        "## Casos que requieren atención",
        "",
    ]
    failures = [item for item in report["tests"]
                if item["status"] in {"failed", "error", "unexpected_success"}]
    for item in failures:
        lines.append(f"- **{item['test']}** ({item['status']})")
        if item.get("detail"):
            lines.append(f"  - {item['detail'].splitlines()[-1][:250]}")
    if not failures:
        lines.append("- Ninguno en la suite determinista.")
    if report["ollama"]["status"] == "failed":
        lines.append(f"- **Ollama:** {report['ollama'].get('reason', 'falló el smoke test')}")
    lines.extend([
        "",
        "## Interpretación",
        "",
        "Una ejecución correcta verifica únicamente los escenarios definidos.",
        "No demuestra exactitud en todos los esquemas, motores ni preguntas.",
        "Los resultados de Gemma se comprueban contra datos sintéticos cuando "
        "se activa expresamente --with-ollama.",
        "",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pruebas de calidad de Kenneth")
    parser.add_argument("--suite", choices=("all", "integration"), default="all",
                        help="all: regresión completa; integration: HTTP + SQLite ficticio")
    parser.add_argument("--report-dir", default="quality_reports",
                        help="Directorio local para report.json y report.md")
    parser.add_argument("--with-ollama", action="store_true",
                        help="Activa una consulta y explicación REALES de Gemma con datos ficticios")
    args = parser.parse_args(argv)

    tests_dir = Path(__file__).resolve().parents[2] / "tests"
    if args.suite == "integration":
        suite = unittest.defaultTestLoader.discover(
            str(tests_dir), pattern="test_assistant_integration.py",
            top_level_dir=str(tests_dir))
    else:
        suite = unittest.defaultTestLoader.discover(
            str(tests_dir), pattern="test_assistant*.py",
            top_level_dir=str(tests_dir))

    started = perf_counter()
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    llm = _run_ollama_smoke() if args.with_ollama else {"status": "not_run"}
    count = result.testsRun
    passed = sum(1 for item in result.records if item["status"] == "passed")
    skipped = len(result.skipped)
    failure_count = len(result.failures) + len(result.unexpectedSuccesses)
    errors = len(result.errors)
    status = "PASS" if result.wasSuccessful() and llm["status"] != "failed" else "FAIL"

    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "suite": args.suite,
        "environment": {"python": platform.python_version(),
                        "platform": platform.system()},
        "scope": {
            "connected_engine": "SQLite disposable synthetic fixture",
            "domains": [item.domain for item in DOMAINS],
            "sqlserver_real": "not_run",
            "postgresql_real": "not_run",
            "external_data": "not_used",
        },
        "summary": {"tests": count, "passed": passed,
                    "failed": failure_count, "errors": errors, "skipped": skipped},
        "duration_ms": round((perf_counter() - started) * 1000, 2),
        "ollama": llm,
        "tests": result.records,
    }
    directory = Path(args.report_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (directory / "report.md").write_text(_markdown_report(report), encoding="utf-8")
    print(f"\nKENNETH QUALITY: {status} ({passed}/{count} pruebas aprobadas)")
    print(f"Informe JSON: {directory / 'report.json'}")
    print(f"Informe legible: {directory / 'report.md'}")
    if args.with_ollama:
        print(f"Gemma/Ollama: {llm['status']}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

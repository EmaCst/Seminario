"""Per-request data-source generation guard.

A process can still have one active engine during the gradual Phase-4
refactor. This guard makes it impossible to return a completed response
silently from a different activation than the request began with.

Browser requests send the opaque X-Kenneth-Source-Revision value previously
received from /api/database/status. Legacy API clients without this header
remain supported but still receive mid-request switch protection.
"""
from starlette.responses import JSONResponse

from app.database.database_manager import database_manager

SOURCE_HEADER = "X-Kenneth-Source-Revision"
EXEMPT_PATHS = {
    "/", "/api/database/status", "/api/database/test",
    "/api/database/test/postgresql",
    "/api/database/connect", "/api/database/connect/postgresql",
    "/api/database/upload/excel", "/api/database/upload/excel/inspect",
    "/api/database/upload/sqlserver-bak",
    "/api/database/upload/postgresql-backup",
    "/api/database/postgresql-backup/settings",
}


def _guarded(path: str) -> bool:
    return (path.startswith("/api/") or path == "/ask-db") and path not in EXEMPT_PATHS


def _changed_response() -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "detail": "La conexión activa cambió. Vuelve a cargar los datos antes de continuar.",
            "code": "SOURCE_CHANGED",
        },
    )


async def source_revision_middleware(request, call_next):
    path = request.url.path
    protected = _guarded(path)
    original = database_manager.status().get("revision") if protected else None
    sent = request.headers.get(SOURCE_HEADER) if protected else None

    if protected and sent is not None and sent != (original or ""):
        response = _changed_response()
    else:
        response = await call_next(request)
        if protected and database_manager.status().get("revision") != original:
            response = _changed_response()

    # No cache or browser back-forward cache should serve data from a
    # previous database; clients still key their React subtree by generation.
    if path.startswith("/api/") or path == "/ask-db":
        response.headers["Cache-Control"] = "no-store, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        revision = database_manager.status().get("revision")
        if revision:
            response.headers[SOURCE_HEADER] = revision
    return response

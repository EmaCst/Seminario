from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.analysis.adaptive_analytics_service import get_adaptive_analytics
from app.analysis.adaptive_dashboard_service import get_adaptive_dashboard_summary
from app.analysis.business_domain_detector import inspect_business_domains
from app.analysis.capability_detector import inspect_capabilities
from app.analysis.dashboard_service import get_dashboard_summary, get_top_products
from app.analysis.semantic_mapper import inspect_semantic_map
from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.ai.gemma import ask_gemma
from app.database.database_manager import database_manager
from app.database.excel_loader import activate_excel_upload, inspect_excel_upload
from app.database.inspector import inspect_database
from app.database.postgresql_backup_loader import (
    backup_upload_enabled, restore_postgresql_backup, runtime_upload_enabled,
    set_backup_upload_enabled,
)
from app.database.sqlserver_backup_loader import restore_sqlserver_backup
from app.ml.predictive_service import detect_monthly_anomalies, forecast_next_months
from app.reports.report_service import REPORT_TYPES, generate_report_pdf
from app.reports.report_configuration import ReportConfiguration, get_report_options, preview_report
from app.reports.configured_pdf import generate_configured_report
from app.services.assistant_service import ask_database
from app.visualizations.semantic_catalog import get_semantic_visualization_catalog
from app.visualizations.visualization_store import (
    SavedVisualizationRequest,
    VisualizationPlacement,
    delete_saved_visualization,
    list_saved_visualizations,
    save_visualization,
    update_visualization_placement,
    update_saved_visualization,
)
from app.visualizations.visualization_service import (
    VisualizationDefinition,
    VisualizationPageRequest,
    explore_visualization,
    get_visualization_catalog,
    get_filter_values,
    preview_visualization,
)

app = FastAPI(title="AI Business Assistant", description="Asistente empresarial para análisis de datos", version="0.13.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ChatMessage(BaseModel):
    role: str
    content: str

class Question(BaseModel):
    question: str
    history: list[ChatMessage] = Field(default_factory=list)

class DatabaseConnectionRequest(BaseModel):
    server: str
    database: str
    username: str | None = None
    password: str | None = None
    driver: str = "ODBC Driver 18 for SQL Server"

class PostgreSQLConnectionRequest(BaseModel):
    host: str
    database: str
    username: str
    password: str | None = None
    port: int = 5432
    sslmode: str = "prefer"

def _current_database_analysis() -> dict:
    schema = inspect_database()
    domain_analysis = inspect_business_domains()
    semantic_model = inspect_semantic_model()
    return {"database": schema.database, "tables": list(schema.tables.keys()), "relationships": len(schema.relationships), "business_domain": {"primary": domain_analysis["primary_domain"], "confidence": domain_analysis["primary_confidence"], "ambiguous": domain_analysis["ambiguous"], "candidates": domain_analysis["candidates"]}, "semantic_model_v2": semantic_model["semantic_model"]}

def _full_connection_analysis(connection_status: dict) -> dict:
    analysis = _current_database_analysis()
    capabilities = inspect_capabilities()
    semantic_map = inspect_semantic_map()
    return {"connected": True, "connection": connection_status, **analysis, "capabilities": capabilities["capabilities"], "semantic_map": semantic_map["semantic_map"]}

@app.get("/")
def root():
    return {"status": "online", "service": "AI Business Assistant", "database": database_manager.status()}

@app.post("/ask")
def ask(question: Question):
    return {"question": question.question, "response": ask_gemma(question.question)}

@app.post("/ask-db")
def ask_database_endpoint(question: Question):
    try:
        return ask_database(question.question, history=[item.model_dump() for item in question.history])
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Kenneth no pudo completar la consulta. Detalle técnico: {exc}") from exc

@app.get("/api/ai/forecast")
def ai_forecast(horizon: int = 3):
    try:
        return forecast_next_months(horizon=horizon)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible generar la predicción: {exc}") from exc

@app.get("/api/ai/anomalies")
def ai_anomalies():
    try:
        return detect_monthly_anomalies()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible detectar anomalías: {exc}") from exc

@app.get("/api/dashboard")
def dashboard():
    return get_dashboard_summary()

@app.get("/api/dashboard/top-products/all")
def dashboard_all_top_products():
    try:
        return get_top_products(limit=None)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible consultar todos los productos: {exc}") from exc

@app.get("/api/dashboard/adaptive")
def adaptive_dashboard():
    try:
        return get_adaptive_dashboard_summary()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible construir el dashboard adaptativo: {exc}") from exc

@app.get("/api/analytics/adaptive")
def adaptive_analytics():
    try:
        return get_adaptive_analytics()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible construir la analítica adaptativa: {exc}") from exc

@app.get("/api/visualizations/semantic-catalog")
def visualization_semantic_catalog():
    try:
        return get_semantic_visualization_catalog()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible construir el catálogo semántico: {exc}") from exc

@app.get("/api/visualizations/saved")
def saved_visualizations(destination: str | None = None):
    return {"items": list_saved_visualizations(destination)}

@app.post("/api/visualizations/saved")
def create_saved_visualization(request: SavedVisualizationRequest):
    try:
        return save_visualization(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.put("/api/visualizations/saved/{visualization_id}")
def edit_saved_visualization(visualization_id: str, request: SavedVisualizationRequest):
    try:
        return update_saved_visualization(visualization_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.put("/api/visualizations/saved/{visualization_id}/placement")
def change_visualization_placement(visualization_id: str, placement: VisualizationPlacement):
    try:
        return update_visualization_placement(visualization_id, placement)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.delete("/api/visualizations/saved/{visualization_id}")
def remove_saved_visualization(visualization_id: str):
    try:
        delete_saved_visualization(visualization_id)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.get("/api/visualizations/filter-values")
def visualization_filter_values(table: str, column: str, search: str = ""):
    try:
        return get_filter_values(table, column, search)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/visualizations/catalog")
def visualization_catalog():
    try:
        return get_visualization_catalog()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible construir el catálogo de visualizaciones: {exc}") from exc

@app.post("/api/visualizations/explore")
def visualization_explore(request: VisualizationPageRequest):
    try:
        return explore_visualization(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible explorar la tabla: {exc}") from exc


@app.post("/api/visualizations/preview")
def visualization_preview(definition: VisualizationDefinition):
    try:
        return preview_visualization(definition)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible generar la visualización: {exc}") from exc

@app.get("/api/reports/options")
def report_configuration_options():
    try:
        return get_report_options()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/reports/preview")
def report_preview(request: ReportConfiguration):
    try:
        return preview_report(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible previsualizar el informe: {exc}") from exc


@app.post("/api/reports/generate")
def report_generate(request: ReportConfiguration):
    try:
        content, filename = generate_configured_report(request)
        return Response(
            content=content, media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible generar el informe: {exc}") from exc


@app.get("/api/reports/pdf")
def report_pdf(type: str = "executive"):
    if type not in REPORT_TYPES:
        raise HTTPException(status_code=422, detail=f"Tipo de reporte no válido. Usa uno de: {', '.join(REPORT_TYPES.keys())}")
    try:
        content, filename = generate_report_pdf(type)
        return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible generar el reporte PDF: {exc}") from exc

@app.get("/api/database/status")
def database_status():
    return database_manager.status()

@app.get("/api/database/domain")
def database_domain():
    try:
        return inspect_business_domains()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible analizar el dominio de la base de datos: {exc}") from exc

@app.get("/api/database/semantic-model")
def database_semantic_model():
    try:
        return inspect_semantic_model()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible construir el modelo semántico: {exc}") from exc

@app.post("/api/database/test")
def test_database_connection(config: DatabaseConnectionRequest):
    try:
        return database_manager.test_connection(**config.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible conectar con SQL Server: {exc}") from exc

@app.post("/api/database/connect")
def connect_database(config: DatabaseConnectionRequest):
    try:
        return _full_connection_analysis(database_manager.configure(**config.model_dump()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible activar la base SQL Server: {exc}") from exc

@app.post("/api/database/test/postgresql")
def test_postgresql_connection(config: PostgreSQLConnectionRequest):
    try:
        return database_manager.test_postgresql_connection(**config.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible conectar con PostgreSQL: {exc}") from exc

@app.post("/api/database/connect/postgresql")
def connect_postgresql_database(config: PostgreSQLConnectionRequest):
    try:
        return _full_connection_analysis(database_manager.configure_postgresql(**config.model_dump()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible activar la base PostgreSQL: {exc}") from exc

@app.post("/api/database/upload/excel/inspect")
async def inspect_excel_file(file: UploadFile = File(...)):
    try:
        return await inspect_excel_upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible interpretar el archivo Excel: {exc}") from exc

@app.post("/api/database/upload/excel")
async def upload_excel_file(file: UploadFile = File(...)):
    """Convierte el libro a SQLite, lo activa y ejecuta la interpretación semántica existente."""
    try:
        imported = await activate_excel_upload(file)
        analysis = _full_connection_analysis(imported["connection"])
        try:
            dashboard = get_adaptive_dashboard_summary()
        except Exception as exc:
            dashboard = {"available": False, "reason": str(exc)}
        return {**imported, **analysis, "dashboard": dashboard}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No fue posible activar el archivo Excel: {exc}") from exc

class BackupUploadSetting(BaseModel):
    enabled: bool


def _local_backup_control(request: Request) -> bool:
    """Only developer-local calls may toggle administrative upload capability.

    Disallow remote clients and foreign origins; no remotely accessible
    unauthenticated toggle is permitted. Deployments need real authentication.
    """
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1"):
        return False
    origin = request.headers.get("origin")
    return origin in ("http://localhost:5173", "http://127.0.0.1:5173")


@app.get("/api/database/postgresql-backup/settings")
def get_postgresql_backup_settings(request: Request):
    return {
        "enabled": backup_upload_enabled(),
        "manageable": _local_backup_control(request),
        "persistent": False,
        "source": "runtime_or_env_default",
    }


@app.put("/api/database/postgresql-backup/settings")
def update_postgresql_backup_settings(settings: BackupUploadSetting, request: Request):
    if not _local_backup_control(request):
        raise HTTPException(
            status_code=403,
            detail=("Por seguridad, la activación desde la interfaz solo está "
                    "disponible en el equipo local, desde el frontend de Kenneth."),
        )
    try:
        enabled = set_backup_upload_enabled(settings.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"enabled": enabled, "manageable": True, "persistent": False,
            "source": "runtime"}


@app.post("/api/database/upload/postgresql-backup")
async def upload_postgresql_archive(request: Request, file: UploadFile = File(...)):
    """Restore a trusted pg_dump archive to a new PostgreSQL database and analyze it."""
    # A localhost checkbox cannot grant remote clients backup-import rights.
    if runtime_upload_enabled() and not _local_backup_control(request):
        await file.close()
        raise HTTPException(
            status_code=403,
            detail="Una carga habilitada desde la casilla local solo puede usarse desde localhost.",
        )
    try:
        restored = await restore_postgresql_backup(file)
        # Restoration and activation have succeeded. An optional visualization
        # or semantic inspection failure must not be reported as RESTORE failure.
        try:
            analysis = _current_database_analysis()
        except Exception as exc:
            analysis = {
                "database": restored["database"],
                "analysis_warning": (
                    "El respaldo se restauró y activó, pero el análisis "
                    f"automático no terminó: {exc}"
                ),
            }
        try:
            adaptive = get_adaptive_dashboard_summary() if "analysis_warning" not in analysis else {
                "available": False, "reason": "Análisis automático pendiente."
            }
        except Exception as exc:
            adaptive = {"available": False, "reason": str(exc)}
        return {"uploaded": True, "engine": "postgresql", "restore": restored,
                **analysis, "dashboard": adaptive}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=("No se pudo restaurar el respaldo PostgreSQL. "
                    "Comprueba que pg_restore esté instalado, que la conexión "
                    "tenga permiso CREATEDB y que el archivo sea de confianza. "
                    f"Detalle: {exc}")
        ) from exc


@app.post("/api/database/upload/sqlserver-bak")
async def upload_sqlserver_backup(file: UploadFile = File(...)):
    try:
        restore_result = await restore_sqlserver_backup(file)
        analysis = _current_database_analysis()
        adaptive = get_adaptive_dashboard_summary()
        return {"uploaded": True, "engine": "sqlserver", "restore": restore_result, **analysis, "dashboard": adaptive}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=("No fue posible restaurar el backup. Verifica permisos para RESTORE DATABASE y DB_RESTORE_DIR. " f"Detalle: {exc}")) from exc

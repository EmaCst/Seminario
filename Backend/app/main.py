from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.analysis.adaptive_dashboard_service import get_adaptive_dashboard_summary
from app.analysis.business_domain_detector import inspect_business_domains
from app.analysis.capability_detector import inspect_capabilities
from app.analysis.dashboard_service import get_dashboard_summary
from app.analysis.semantic_mapper import inspect_semantic_map
from app.analysis.semantic_mapper_v2 import inspect_semantic_model
from app.ai.gemma import ask_gemma
from app.database.database_manager import database_manager
from app.database.inspector import inspect_database
from app.database.sqlserver_backup_loader import restore_sqlserver_backup
from app.services.assistant_service import ask_database


app = FastAPI(
    title="AI Business Assistant",
    description="Asistente empresarial para análisis de datos",
    version="0.6.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Question(BaseModel):
    question: str


class DatabaseConnectionRequest(BaseModel):
    server: str
    database: str
    username: str | None = None
    password: str | None = None
    driver: str = "ODBC Driver 18 for SQL Server"


def _current_database_analysis() -> dict:
    schema = inspect_database()
    domain_analysis = inspect_business_domains()
    semantic_model = inspect_semantic_model()

    return {
        "database": schema.database,
        "tables": list(schema.tables.keys()),
        "relationships": len(schema.relationships),
        "business_domain": {
            "primary": domain_analysis["primary_domain"],
            "confidence": domain_analysis["primary_confidence"],
            "ambiguous": domain_analysis["ambiguous"],
            "candidates": domain_analysis["candidates"],
        },
        "semantic_model_v2": semantic_model["semantic_model"],
    }


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "AI Business Assistant",
        "database": database_manager.status(),
    }


@app.post("/ask")
def ask(question: Question):
    response = ask_gemma(question.question)
    return {"question": question.question, "response": response}


@app.post("/ask-db")
def ask_database_endpoint(question: Question):
    return ask_database(question.question)


@app.get("/api/dashboard")
def dashboard():
    return get_dashboard_summary()


@app.get("/api/dashboard/adaptive")
def adaptive_dashboard():
    try:
        return get_adaptive_dashboard_summary()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"No fue posible construir el dashboard adaptativo: {exc}"
        ) from exc


@app.get("/api/database/status")
def database_status():
    return database_manager.status()


@app.get("/api/database/domain")
def database_domain():
    try:
        return inspect_business_domains()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"No fue posible analizar el dominio de la base de datos: {exc}"
        ) from exc


@app.get("/api/database/semantic-model")
def database_semantic_model():
    try:
        return inspect_semantic_model()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"No fue posible construir el modelo semántico: {exc}"
        ) from exc


@app.post("/api/database/test")
def test_database_connection(config: DatabaseConnectionRequest):
    try:
        return database_manager.test_connection(**config.model_dump())
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"No fue posible conectar con la base de datos: {exc}"
        ) from exc


@app.post("/api/database/connect")
def connect_database(config: DatabaseConnectionRequest):
    try:
        connection_status = database_manager.configure(**config.model_dump())
        analysis = _current_database_analysis()
        capabilities = inspect_capabilities()
        semantic_map = inspect_semantic_map()

        return {
            "connected": True,
            "connection": connection_status,
            **analysis,
            "capabilities": capabilities["capabilities"],
            "semantic_map": semantic_map["semantic_map"],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"No fue posible activar la base de datos: {exc}"
        ) from exc


@app.post("/api/database/upload/sqlserver-bak")
async def upload_sqlserver_backup(file: UploadFile = File(...)):
    """Carga un .bak, lo restaura en la instancia SQL Server configurada y lo analiza."""
    try:
        restore_result = await restore_sqlserver_backup(file)
        analysis = _current_database_analysis()
        adaptive = get_adaptive_dashboard_summary()

        return {
            "uploaded": True,
            "engine": "sqlserver",
            "restore": restore_result,
            **analysis,
            "dashboard": adaptive,
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "No fue posible restaurar el backup. Verifica que la cuenta usada por el backend "
                "tenga permisos para RESTORE DATABASE y que SQL Server pueda leer DB_RESTORE_DIR. "
                f"Detalle: {exc}"
            ),
        ) from exc

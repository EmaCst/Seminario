from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.assistant_service import ask_database
from app.ai.gemma import ask_gemma


app = FastAPI(
    title="AI Business Assistant",
    description="Asistente empresarial para análisis de datos",
    version="0.1.0"
)


# ==========================================
# CORS
# ==========================================

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


# ==========================================
# MODELOS
# ==========================================

class Question(BaseModel):
    question: str


# ==========================================
# ENDPOINTS
# ==========================================

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "AI Business Assistant"
    }


@app.post("/ask")
def ask(question: Question):

    response = ask_gemma(question.question)

    return {
        "question": question.question,
        "response": response
    }


@app.post("/ask-db")
def ask_database_endpoint(question: Question):

    result = ask_database(
        question.question
    )

    return result
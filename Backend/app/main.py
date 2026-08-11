from fastapi import FastAPI
from pydantic import BaseModel

from app.ai.gemma import ask_gemma


app = FastAPI(
    title="AI Business Assistant",
    description="Asistente empresarial para análisis de datos",
    version="0.1.0"
)


class Question(BaseModel):
    question: str


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
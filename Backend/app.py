"""
Entrypoint HTTP del agente (FastAPI).

Capa de I/O: no sabe nada de LLMs, prompts ni vector stores. Solo conoce la API
pública de agent.py y chat_history/.

Endpoints:
    GET  /health  → estado del servicio
    POST /chat    → {"thread_id": "...", "mensaje": "..."}
                  → {"respuesta": "...", "tools_usadas": [...], "graficos": [...]}

Cada gráfico llega como PNG en base64 (imagen_base64), listo para
<img src="data:image/png;base64,...">. El archivo queda además en
graficos_generados/<thread_id>/.

Ejecutar:
    uvicorn app:app --reload --port 8000

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import base64
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import agent
from chat_history import log_mensaje

load_dotenv(find_dotenv())

# ============================================
# CONSTANTES
# ============================================
# Todas las variables que usa el proyecto, incluidas las de tools/: que falte
# una debe romper el arranque, no un request en producción.
VARIABLES_REQUERIDAS = (
    "OPENAI_API_KEY",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "GOOGLE_APPLICATION_CREDENTIALS",
)


def verificar_configuracion() -> None:
    """Falla rápido si falta alguna variable de entorno obligatoria."""
    faltantes = [v for v in VARIABLES_REQUERIDAS if not os.getenv(v)]
    if faltantes:
        raise RuntimeError(f"❌ Faltan variables en .env: {', '.join(faltantes)}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    verificar_configuracion()
    agent.init_resources()
    yield
    agent.close_resources()


app = FastAPI(title="Agente Text-to-SQL CitiBike", lifespan=lifespan)


# ============================================
# ESQUEMAS
# ============================================
class ChatRequest(BaseModel):
    thread_id: str = Field(..., min_length=1, description="ID estable de la conversación o del contacto")
    mensaje: str = Field(..., min_length=1)


class GraficoResponse(BaseModel):
    titulo: str
    descripcion: str
    tipo: str
    imagen_base64: str


class ChatResponse(BaseModel):
    respuesta: str
    tools_usadas: list[str]
    graficos: list[GraficoResponse] = []


# ============================================
# ENDPOINTS
# ============================================
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# `def` (no `async def`): el checkpointer es síncrono y FastAPI lo corre en su
# threadpool, sin bloquear el event loop.
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    # Se registra antes de invocar: si el turno falla, queda constancia de la pregunta
    log_mensaje(req.thread_id, "user", req.mensaje)
    try:
        respuesta, tools_usadas, graficos = agent.responder(req.thread_id, req.mensaje)
    except Exception as e:
        print(f"❌ Error en el turno de {req.thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Error al procesar el mensaje")
    log_mensaje(req.thread_id, "assistant", respuesta, tools_usadas)
    return ChatResponse(
        respuesta=respuesta,
        tools_usadas=tools_usadas,
        graficos=[
            GraficoResponse(
                titulo=g["titulo"],
                descripcion=g["descripcion"],
                tipo=g["tipo"],
                imagen_base64=base64.b64encode(Path(g["archivo"]).read_bytes()).decode(),
            )
            for g in graficos
        ],
    )

"""
Orquestador del agente Text-to-SQL: ensambla LLM + prompt + tools + memoria.

- Recursos pesados (LLMs, checkpointer, prompts, subagente) se
  inicializan UNA vez en init_resources().
- El agente se reconstruye por mensaje en build_agent(): es barato y permite
  que el prompt del turno dependa del hueco desde el último mensaje.

Subagentes: el de gráficos (subagentes/graficos/) se invoca como la tool
generar_graficos. Los datos le llegan por el estado (estado.py), no por el
texto del LLM.

Middleware, en este orden (resumir antes de descartar gastaría una llamada al
LLM en mensajes que están por borrarse):
  1. retención   → descarta mensajes más viejos que memory.retention_days
  2. resumen     → SummarizationMiddleware al superar memory.token_limit
  3. prompt      → system prompt con fecha/hora y, si el usuario vuelve tras
                   memory.reengagement_hours, el aviso de retoma (transitorio)

Config: model_config/model.yaml · Prompts: prompt/

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import yaml
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    ModelRequest,
    SummarizationMiddleware,
    before_model,
    dynamic_prompt,
)
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

from chat_history import close_store, init_chat_history, ultimo_checkpoint_ts
from estado import EstadoAgente
from subagentes.graficos import init_subagente_graficos
from tools import get_bigquery_tool, get_graficos_tool

# ============================================
# CONSTANTES
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_CONFIG_PATH = os.path.join(BASE_DIR, "model_config", "model.yaml")
SYSTEM_PROMPT_PATH = os.path.join(BASE_DIR, "prompt", "system_prompt.yaml")
GRAFICOS_PROMPT_PATH = os.path.join(BASE_DIR, "prompt", "graficos_prompt.yaml")

BLOQUE_RETOMA = """

<Retoma_De_Conversacion>
El usuario vuelve después de {horas} horas sin escribir. Salúdalo de nuevo
brevemente y retoma con naturalidad. Si vuelve sobre cifras que le diste
antes, recuérdalas desde el historial; solo vuelve a consultar BigQuery si
pide un dato nuevo o un periodo distinto.
</Retoma_De_Conversacion>"""

# Singletons de módulo: se llenan en init_resources()
_llm = None
_bigquery_tool = None
_graficos_tool = None
_checkpointer = None
_system_prompt: str = ""
_memory_cfg: dict = {}
_agent_cfg: dict = {}


# ============================================
# CARGA DE CONFIGURACIÓN
# ============================================
def _cargar_yaml(ruta: str) -> dict:
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def init_resources() -> None:
    """Una vez al arrancar. Deja singletons de módulo."""
    global _llm, _bigquery_tool, _graficos_tool, _checkpointer
    global _system_prompt, _memory_cfg, _agent_cfg

    model_cfg = _cargar_yaml(MODEL_CONFIG_PATH)
    _memory_cfg = model_cfg["memory"]
    _agent_cfg = model_cfg["agent"]

    llm_cfg = model_cfg["llm"]
    _llm = init_chat_model(
        llm_cfg["model"],
        model_provider=llm_cfg["provider"],
        temperature=llm_cfg["temperature"],
    )

    _system_prompt = _cargar_yaml(SYSTEM_PROMPT_PATH)["system_prompt"].replace(
        "{bot_name}", _agent_cfg["bot_name"]
    )

    init_subagente_graficos(
        model_cfg["subagentes"]["graficos"],
        _cargar_yaml(GRAFICOS_PROMPT_PATH)["system_prompt"],
    )

    _checkpointer = init_chat_history()
    _bigquery_tool = get_bigquery_tool()
    _graficos_tool = get_graficos_tool()


def close_resources() -> None:
    """Libera las conexiones al apagar la app."""
    close_store()


# ============================================
# MIDDLEWARE
# ============================================
def _es_resumen(m) -> bool:
    return (m.additional_kwargs or {}).get("lc_source") == "summarization"


@before_model
def descartar_vencidos(state: AgentState, runtime: Runtime) -> dict | None:
    """Retención por edad: corta en el primer mensaje humano vigente.

    Corta en frontera de mensaje humano para no dejar ToolMessages huérfanos
    (400 del proveedor). Los mensajes sin "ts" se tratan como vigentes, y el
    mensaje-resumen se conserva.
    """
    limite = datetime.now(timezone.utc) - timedelta(days=_memory_cfg["retention_days"])
    mensajes = state["messages"]
    corte = None
    for i, m in enumerate(mensajes):
        if m.type != "human" or _es_resumen(m):
            continue
        ts = (m.additional_kwargs or {}).get("ts")
        if ts is None or datetime.fromisoformat(ts) >= limite:
            corte = i
            break
    if corte is None or corte == 0:
        return None
    resumenes = [m for m in mensajes[:corte] if _es_resumen(m)]
    return {
        "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *resumenes, *mensajes[corte:]]
    }


def _contexto_fecha_hora() -> str:
    ahora = datetime.now(ZoneInfo(_agent_cfg["timezone"]))
    return ahora.strftime("%A %d/%m/%Y, %H:%M") + f" ({_agent_cfg['timezone']})"


def _prompt_middleware(horas_ausente: float | None):
    """System prompt del turno. Transitorio: nada de esto se guarda en el historial."""

    @dynamic_prompt
    def prompt_del_turno(request: ModelRequest) -> str:
        prompt = _system_prompt.replace("{fecha_hora}", _contexto_fecha_hora())
        if horas_ausente is not None and horas_ausente >= _memory_cfg["reengagement_hours"]:
            prompt += BLOQUE_RETOMA.format(horas=int(horas_ausente))
        return prompt

    return prompt_del_turno


# ============================================
# AGENTE POR MENSAJE
# ============================================
def build_agent(thread_id: str):
    """Por cada mensaje. Barato: el prompt del turno depende del hueco desde el último mensaje."""
    ultimo = ultimo_checkpoint_ts(thread_id)
    horas_ausente = (
        (datetime.now(timezone.utc) - ultimo).total_seconds() / 3600 if ultimo else None
    )

    return create_agent(
        model=_llm,
        tools=[_bigquery_tool, _graficos_tool],
        state_schema=EstadoAgente,
        checkpointer=_checkpointer,
        middleware=[
            descartar_vencidos,
            SummarizationMiddleware(
                model=_llm,
                trigger=("tokens", _memory_cfg["token_limit"]),
                keep=("messages", _memory_cfg["keep_messages"]),
            ),
            _prompt_middleware(horas_ausente),
        ],
    )


def _tools_del_turno(mensajes: list) -> list[str]:
    """Nombres de las tools que el modelo invocó desde el último mensaje humano."""
    usadas = []
    for m in reversed(mensajes):
        if isinstance(m, HumanMessage):
            break
        if isinstance(m, AIMessage):
            usadas.extend(tc["name"] for tc in m.tool_calls)
    return list(reversed(usadas))


def responder(thread_id: str, texto: str) -> tuple[str, list[str], list[dict]]:
    """Procesa un mensaje del usuario.

    Devuelve (respuesta, tools usadas en el turno, gráficos del turno). Cada
    gráfico es {"titulo", "descripcion", "tipo", "archivo"} con la ruta del PNG.
    """
    agente = build_agent(thread_id)
    mensaje = HumanMessage(
        content=texto,
        additional_kwargs={"ts": datetime.now(timezone.utc).isoformat()},
    )
    resultado = agente.invoke(
        # graficos_turno se reinicia: solo cuentan los gráficos de este turno
        {"messages": [mensaje], "graficos_turno": []},
        config={"configurable": {"thread_id": thread_id}},
    )
    mensajes = resultado["messages"]
    return mensajes[-1].text, _tools_del_turno(mensajes), resultado.get("graficos_turno", [])

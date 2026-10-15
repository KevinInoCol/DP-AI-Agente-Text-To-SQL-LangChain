"""Persistencia de la conversación: checkpointer (estado) + log plano (auditoría).

Las dos piezas van siempre juntas: init_chat_history() crea ambas y verifica que
existan antes de que el agente atienda el primer mensaje.
"""

from langgraph.checkpoint.postgres import PostgresSaver

from chat_history.conversation_log import TABLA_LOG, crear_tabla_log, log_mensaje
from chat_history.postgres_store import (
    TABLAS_CHECKPOINTER,
    close_store,
    get_pool,
    init_store,
    ultimo_checkpoint_ts,
    verificar_tablas,
)


def init_chat_history() -> PostgresSaver:
    """Checkpointer + tabla plana, creados y verificados. Idempotente."""
    checkpointer = init_store()
    crear_tabla_log()
    verificar_tablas((*TABLAS_CHECKPOINTER, TABLA_LOG))
    return checkpointer


__all__ = [
    "close_store",
    "get_pool",
    "init_chat_history",
    "log_mensaje",
    "ultimo_checkpoint_ts",
]

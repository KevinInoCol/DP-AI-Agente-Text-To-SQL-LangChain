"""
Log plano de la conversación en PostgreSQL: una fila por mensaje, legible con SQL.

Complementa al checkpointer (no lo reemplaza): sirve para reportes, QA y
auditoría, y es el único registro fiel de lo que se dijo cuando el resumen o la
retención recortan el historial del agente.

El DDL vive en migraciones_SQL/001_chat_log.sql (fuente única): crear_tabla_log()
lo ejecuta al arrancar, así la tabla existe aunque nadie haya corrido la
migración a mano. Las escrituras son fire-and-forget: si falla el log, el
usuario igual recibe su respuesta.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

from pathlib import Path

from chat_history.postgres_store import get_pool

# ============================================
# CONSTANTES
# ============================================
TABLA_LOG = "chat_log"
MIGRACION_LOG = Path(__file__).resolve().parent.parent / "migraciones_SQL" / "001_chat_log.sql"


# ============================================
# FUNCIONES PÚBLICAS
# ============================================
def crear_tabla_log() -> None:
    """Crea chat_log con su índice y RLS ejecutando la migración (idempotente)."""
    pool = get_pool()
    if pool is None:
        raise RuntimeError("❌ Llama a init_store() antes de crear_tabla_log()")
    # Una sentencia por execute(): psycopg no admite varias en un mismo
    # comando ("cannot insert multiple commands into a prepared statement").
    sentencias = [s.strip() for s in MIGRACION_LOG.read_text(encoding="utf-8").split(";")]
    with pool.connection() as conn:
        for sentencia in filter(None, sentencias):
            conn.execute(sentencia)


def log_mensaje(
    thread_id: str,
    rol: str,
    contenido: str,
    tools_usadas: list[str] | None = None,
) -> None:
    """Registra un mensaje en chat_log. Nunca lanza excepción."""
    pool = get_pool()
    if pool is None:
        return
    try:
        with pool.connection() as conn:
            conn.execute(
                "INSERT INTO chat_log (thread_id, rol, contenido, tools_usadas) "
                "VALUES (%s, %s, %s, %s)",
                (thread_id, rol, contenido, tools_usadas or None),
            )
    except Exception as e:
        print(f"⚠️ No se pudo registrar el mensaje en chat_log: {e}")

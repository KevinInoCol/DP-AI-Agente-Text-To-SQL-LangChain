"""
Checkpointer de LangGraph sobre PostgreSQL (memoria de corto plazo del agente).

Guarda el estado completo de cada hilo (thread_id): mensajes, tool calls y
resultados de tools. Es lo que el agente recarga en cada turno. Los mensajes
van serializados en binario: para leer conversaciones con SQL usa la tabla
plana de conversation_log.py.

También es dueño del pool de conexiones que comparte con el log plano. Un pool
(y no una conexión suelta) porque el proveedor cierra las conexiones inactivas
y psycopg no reconecta solo: con una conexión única, el bot deja de responder
en silencio hasta reiniciar el proceso.

Requeridas en .env: DB_USER, DB_PASSWORD, DB_HOST
Opcionales: DB_PORT (5432), DB_NAME (postgres)

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
from datetime import datetime
from urllib.parse import quote_plus

from dotenv import find_dotenv, load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

load_dotenv(find_dotenv())

# ============================================
# VARIABLES DE ENTORNO
# ============================================
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")

# ============================================
# CONSTANTES
# ============================================
TABLAS_CHECKPOINTER = (
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
)

# Singletons de módulo: se crean UNA vez en init_store()
_pool: ConnectionPool | None = None
_checkpointer: PostgresSaver | None = None


# ============================================
# FUNCIONES PÚBLICAS
# ============================================
def build_database_url() -> str:
    """URL de conexión. La contraseña va escapada: puede traer @, : o /."""
    if not all([DB_USER, DB_PASSWORD, DB_HOST]):
        raise ValueError(
            "❌ Faltan variables de base de datos en .env\n"
            "Requeridas: DB_USER, DB_PASSWORD, DB_HOST"
        )
    return f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def init_store() -> PostgresSaver:
    """Abre el pool, crea/migra las tablas del checkpointer y les activa RLS.

    Idempotente. RLS sin políticas cierra el acceso por PostgREST (anon key de
    Supabase); el agente no se ve afectado porque conecta con el rol dueño.
    """
    global _pool, _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    print(f"🔌 Conectando como: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

    # - autocommit: lo exige PostgresSaver (su setup crea índices fuera de transacción)
    # - prepare_threshold=0: obligatorio detrás de un pooler en modo transacción
    #   (Supabase 6543 / PgBouncer); sin él, "prepared statement already exists"
    # - connect_timeout / timeout: que una base caída no cuelgue el arranque
    _pool = ConnectionPool(
        build_database_url(),
        min_size=1,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0, "connect_timeout": 5},
        timeout=5,
        check=ConnectionPool.check_connection,
        open=True,
    )
    _checkpointer = PostgresSaver(_pool)
    _checkpointer.setup()
    with _pool.connection() as conn:
        for tabla in TABLAS_CHECKPOINTER:
            conn.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
    return _checkpointer


def verificar_tablas(tablas: tuple[str, ...]) -> None:
    """Falla al arrancar si falta alguna tabla, o si alguna no tiene RLS activado."""
    with _pool.connection() as conn:
        filas = conn.execute(
            "SELECT relname, relrowsecurity FROM pg_class "
            "WHERE oid = ANY(SELECT to_regclass(t) FROM unnest(%s::text[]) AS t)",
            (list(tablas),),
        ).fetchall()
    encontradas = {nombre: rls for nombre, rls in filas}
    faltantes = [t for t in tablas if t not in encontradas]
    sin_rls = [t for t, rls in encontradas.items() if not rls]
    if faltantes or sin_rls:
        raise RuntimeError(
            f"❌ Memoria incompleta. Faltan tablas: {faltantes or '-'} · Sin RLS: {sin_rls or '-'}"
        )
    print(f"✅ Memoria lista: {', '.join(tablas)} (con RLS)")


def get_pool() -> ConnectionPool | None:
    """Pool compartido. None si init_store() aún no se llamó."""
    return _pool


def ultimo_checkpoint_ts(thread_id: str) -> datetime | None:
    """Momento del último checkpoint del hilo. None = primera conversación."""
    if _checkpointer is None:
        return None
    tupla = _checkpointer.get_tuple({"configurable": {"thread_id": thread_id}})
    if tupla is None:
        return None
    return datetime.fromisoformat(tupla.checkpoint["ts"])


def close_store() -> None:
    """Cierra el pool al apagar la app."""
    global _pool, _checkpointer
    if _pool is not None:
        _pool.close()
    _pool = None
    _checkpointer = None

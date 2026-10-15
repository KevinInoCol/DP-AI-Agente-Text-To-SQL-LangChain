"""
Tool: búsqueda en la base de conocimiento (RAG con Qdrant).

El par (modelo de embeddings, colección) NO se define acá: viene de
vector_store.py, la fuente única. Así la consulta no puede desalinearse de la
ingesta (RAG/rag.py).

Tool compartida: no depende del thread_id, así que se construye UNA vez en
agent.init_resources(), no por mensaje.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

from langchain.tools import tool

from vector_store import COLLECTION_NAME, get_vectorstore

# ============================================
# CONSTANTES
# ============================================
# Fragmentos a recuperar por consulta.
TOP_K = 5


# ============================================
# FUNCIÓN IMPERATIVA
# ============================================
def buscar_base_conocimiento(vectorstore, consulta: str, top_k: int = TOP_K) -> str:
    """Búsqueda semántica. Devuelve texto para el modelo; nunca lanza."""
    try:
        docs = vectorstore.similarity_search(consulta, k=top_k)
    except Exception as e:
        return (
            f"Error al consultar la base de conocimiento ({COLLECTION_NAME}): {e}. "
            "Avisa al usuario que no pudiste verificar la información ahora."
        )

    if not docs:
        return (
            "No encontré información sobre eso en la base de conocimiento. "
            "No inventes una respuesta: dile al usuario que no tienes ese dato."
        )

    contexto = "Información encontrada en la base de conocimiento:\n\n"
    for i, doc in enumerate(docs, 1):
        contexto += f"[{i}]\n{doc.page_content}\n\n"
    return contexto


# ============================================
# FACTORY
# ============================================
def get_retrieval_tool():
    """Construye el vector store UNA vez y devuelve la tool que lo consulta.

    Si la colección aún no existe (no se corrió RAG/rag.py), el agente arranca
    igual y la tool responde con un aviso en vez de tumbar la app.
    """
    try:
        vectorstore = get_vectorstore()
    except Exception as e:
        print(f"⚠️ Base de conocimiento no disponible ({COLLECTION_NAME}): {e}")
        vectorstore = None

    @tool("buscar_base_conocimiento")
    def buscar_base_conocimiento_tool(consulta: str) -> str:
        """Consulta la base de conocimiento del negocio. Es la ÚNICA fuente válida
        de datos del negocio: productos, servicios, precios, políticas, horarios,
        requisitos y procedimientos.

        Úsala SIEMPRE antes de responder cualquier pregunta sobre el negocio.
        No la uses para saludos ni charla general.

        Args:
            consulta: la pregunta o tema a buscar, en lenguaje natural
                (ej: 'horario de atención', 'política de devoluciones').
        """
        if vectorstore is None:
            return (
                "La base de conocimiento no está disponible. Dile al usuario que "
                "no puedes verificar la información ahora."
            )
        print(f"   🔍 Buscando en la base de conocimiento: '{consulta}'")
        return buscar_base_conocimiento(vectorstore, consulta)

    return buscar_base_conocimiento_tool

"""
Configuración del Vector Store (Qdrant). FUENTE ÚNICA del par (embedding, colección).

La ingesta (RAG/rag.py) y la consulta (tools/retrieval.py) importan de acá. El
modelo de embeddings y el nombre de la colección NO se escriben en ningún otro
archivo.

Por qué importa: si la ingesta indexa con un modelo y la consulta busca con otro,
la búsqueda devuelve resultados vacíos o irrelevantes SIN lanzar ningún error.

Requeridas en .env: QDRANT_URL, OPENAI_API_KEY
Opcionales: QDRANT_API_KEY, QDRANT_COLLECTION (default: tenant_id_datapath)

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os

from dotenv import find_dotenv, load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

load_dotenv(find_dotenv())

# ============================================
# VARIABLES DE ENTORNO
# ============================================
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# Convención multi-tenant: prefijo tenant_id_ (guiones bajos en Qdrant)
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "tenant_id_datapath")

# ============================================
# CONSTANTES
# ============================================
# Un solo modelo para todo el proyecto. Cambiarlo obliga a REINDEXAR: la
# dimensión del vector es parte de la definición de la colección.
MODELO_EMBEDDING = "text-embedding-3-small"


# ============================================
# FUNCIONES PÚBLICAS
# ============================================
def get_embedding_model() -> OpenAIEmbeddings:
    """Modelo de embeddings. El mismo para ingestar y para consultar."""
    return OpenAIEmbeddings(model=MODELO_EMBEDDING)


def get_client() -> QdrantClient:
    """Cliente de Qdrant.

    port=None: sin eso qdrant-client le agrega :6333 a la URL, y detrás de un
    proxy https (EasyPanel, Qdrant Cloud) la conexión muere con
    "Connection refused".
    """
    if not QDRANT_URL:
        raise ValueError("❌ Falta QDRANT_URL en .env")
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, port=None)


def get_vectorstore() -> QdrantVectorStore:
    """Vector store listo para consultar la colección del tenant."""
    return QdrantVectorStore(
        client=get_client(),
        collection_name=COLLECTION_NAME,
        embedding=get_embedding_model(),
    )

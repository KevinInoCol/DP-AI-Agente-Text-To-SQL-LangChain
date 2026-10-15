"""
Ingesta de la base de conocimiento en Qdrant (reindexado completo).

Loader → splitter → embeddings → vector store. Lee los .pdf, .txt y .md de
RAG/Base_de_Conocimiento/, BORRA la colección si existe y la vuelve a crear.

El par (modelo de embeddings, colección) viene de vector_store.py. La config de
retrieval (top_k) NO vive aquí: vive en tools/retrieval.py.

Ejecutar desde la raíz del proyecto:
    python RAG/rag.py

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
import sys
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client.models import Distance, VectorParams

# La raíz del proyecto al path: vector_store.py vive un nivel arriba de RAG/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validacion_nombre_tenant_id import validar_qdrant  # noqa: E402
from vector_store import (  # noqa: E402
    COLLECTION_NAME,
    MODELO_EMBEDDING,
    get_client,
    get_embedding_model,
    get_vectorstore,
)

# ============================================
# CONSTANTES
# ============================================
CARPETA_DOCUMENTOS = Path(__file__).parent / "Base_de_Conocimiento"
EXTENSIONES = {".pdf", ".txt", ".md"}
TAMANO_CHUNK = 1000
SOLAPAMIENTO_CHUNK = 200


def verificar_configuracion() -> None:
    """Falla antes de gastar embeddings si algo no cuadra."""
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("❌ Falta OPENAI_API_KEY en .env")
    resultado = validar_qdrant(COLLECTION_NAME)
    if not resultado.ok:
        raise ValueError(f"❌ Nombre de colección inválido:\n{resultado}")
    if not any(p.suffix.lower() in EXTENSIONES for p in CARPETA_DOCUMENTOS.iterdir()):
        raise FileNotFoundError(
            f"❌ No hay documentos ({', '.join(sorted(EXTENSIONES))}) en {CARPETA_DOCUMENTOS}"
        )


def cargar_documentos() -> list:
    documentos = []
    for ruta in sorted(CARPETA_DOCUMENTOS.iterdir()):
        sufijo = ruta.suffix.lower()
        if sufijo == ".pdf":
            documentos.extend(PyPDFLoader(str(ruta)).load())
        elif sufijo in {".txt", ".md"}:
            documentos.extend(TextLoader(str(ruta), encoding="utf-8").load())
        else:
            continue
        print(f"   📄 {ruta.name}")
    return documentos


def recrear_coleccion() -> None:
    """Borra y crea la colección con la dimensión del modelo de embeddings."""
    client = get_client()
    dimension = len(get_embedding_model().embed_query("dimension"))
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
    )


def main() -> None:
    print(f"📚 Cargando documentos de {CARPETA_DOCUMENTOS}")
    documentos = cargar_documentos()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=TAMANO_CHUNK, chunk_overlap=SOLAPAMIENTO_CHUNK
    )
    chunks = splitter.split_documents(documentos)
    print(f"✂️  {len(documentos)} documentos → {len(chunks)} chunks")

    print(f"🗂️  Recreando colección '{COLLECTION_NAME}' ({MODELO_EMBEDDING})")
    recrear_coleccion()

    get_vectorstore().add_documents(chunks)
    print(f"✅ {len(chunks)} chunks indexados en '{COLLECTION_NAME}'")


if __name__ == "__main__":
    verificar_configuracion()
    main()

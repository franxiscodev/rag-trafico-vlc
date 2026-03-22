"""
Pipeline de ingesta: descarga → categoriza → embedd → indexa en Qdrant.

Estrategia: borrado + recreación completa de la colección en cada ciclo.
Embedding: Gemini Embedding 001 (3072 dims) vía LlamaIndex.
Reintentos: tenacity para gestionar errores 429 de la API Gemini.
"""
import os
import logging
from dotenv import load_dotenv
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from llama_index.core import Document
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.core import Settings, VectorStoreIndex

from ingesta.api_client import fetch_all_records
from ingesta.categorizer import categorize, build_document_text
from app.qdrant_store import (
    get_qdrant_client,
    ensure_collection,
    get_storage_context,
    COLLECTION,
    VECTOR_SIZE,
)
from qdrant_client.models import Distance, VectorParams, HnswConfigDiff

load_dotenv()
log = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
EMBED_MODEL = "models/embedding-001"
HNSW_M = 16


def _build_documents(records: list[dict]) -> list[Document]:
    """Convierte los registros de la API en Documents de LlamaIndex."""
    docs = []
    for rec in records:
        nombre = rec.get("denominacion") or ""
        categoria = categorize(nombre)
        texto = build_document_text(rec)
        doc = Document(
            text=texto,
            metadata={
                "source": categoria,
                "denominacion": nombre,
                "idtramo": rec.get("idtramo"),
                "estado": rec.get("estado"),
                "lat": (rec.get("geo_point_2d") or {}).get("lat"),
                "lon": (rec.get("geo_point_2d") or {}).get("lon"),
            },
        )
        docs.append(doc)
    return docs


def _drop_and_recreate(client) -> None:
    """Borra la colección existente y la recrea vacía."""
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION in existing:
        client.delete_collection(COLLECTION)
        log.info("Coleccion '%s' borrada.", COLLECTION)
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        hnsw_config=HnswConfigDiff(m=HNSW_M),
    )
    log.info("Coleccion '%s' recreada.", COLLECTION)


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def run_ingesta() -> int:
    """
    Ejecuta el ciclo completo de ingesta.
    Devuelve el número de documentos indexados.
    """
    log.info("Iniciando ciclo de ingesta...")

    # 1. Configurar embedding
    embed_model = GeminiEmbedding(
        model_name=EMBED_MODEL,
        api_key=GEMINI_API_KEY,
    )
    Settings.embed_model = embed_model

    # 2. Descargar datos
    records = fetch_all_records()
    log.info("Descargados %d registros de la API.", len(records))

    # 3. Construir documentos
    docs = _build_documents(records)

    # Resumen de categorías
    from collections import Counter
    conteo = Counter(d.metadata["source"] for d in docs)
    log.info("Categorias: %s", dict(conteo))

    # 4. Borrar + recrear colección
    client = get_qdrant_client()
    _drop_and_recreate(client)

    # 5. Indexar en Qdrant
    storage_context = get_storage_context(client)
    VectorStoreIndex.from_documents(
        docs,
        storage_context=storage_context,
        show_progress=True,
    )

    log.info("Ingesta completada: %d documentos indexados.", len(docs))
    return len(docs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    total = run_ingesta()
    print(f"[OK] {total} documentos indexados en Qdrant.")

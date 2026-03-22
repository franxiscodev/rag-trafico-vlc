"""
Pipeline de ingesta: descarga → categoriza → embedd → indexa en Qdrant.

Estrategia: borrado + recreación completa de la colección en cada ciclo.
Embedding: gemini-embedding-001 (3072 dims) vía llama-index-embeddings-google-genai.
Reintentos 429: gestionados internamente por GoogleGenAIEmbedding (retries + backoff).
Preflight check: antes de borrar Qdrant se embedd 1 doc de prueba; si hay 429
  se aborta la ingesta conservando la colección intacta.
"""
import logging
from collections import Counter
from dotenv import load_dotenv

from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from qdrant_client.models import Distance, VectorParams, HnswConfigDiff

from ingesta.api_client import fetch_all_records
from ingesta.categorizer import categorize, build_document_text
from app.qdrant_store import (
    get_qdrant_client,
    get_storage_context,
    COLLECTION,
    VECTOR_SIZE,
)

load_dotenv()
log = logging.getLogger(__name__)

EMBED_MODEL = "gemini-embedding-001"
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


def _preflight_embedding_check(embed_model: GoogleGenAIEmbedding) -> None:
    """
    Embedd un texto mínimo para verificar que la API de Gemini acepta peticiones.
    Lanza google.api_core.exceptions.ResourceExhausted si hay 429,
    lo que aborta la ingesta antes de tocar Qdrant.
    """
    from google.api_core.exceptions import ResourceExhausted
    log.info("Preflight check: probando disponibilidad de la API de embedding...")
    try:
        embed_model.get_text_embedding("test")
        log.info("Preflight OK — API de embedding disponible.")
    except ResourceExhausted as exc:
        log.error(
            "Preflight FALLIDO: 429 ResourceExhausted. "
            "Ingesta abortada — Qdrant conserva los datos anteriores. Error: %s",
            exc,
        )
        raise


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


def run_ingesta() -> int:
    """
    Ejecuta el ciclo completo de ingesta.
    Devuelve el número de documentos indexados.

    Los reintentos por 429 los gestiona GoogleGenAIEmbedding internamente
    (retries=10, backoff exponencial hasta 60 s). No se usa tenacity aquí
    para evitar que un 429 reinicie todo el pipeline (borrado + descarga).
    """
    log.info("Iniciando ciclo de ingesta...")

    # 1. Configurar embedding con reintentos generosos para gestionar 429
    #    GOOGLE_API_KEY se detecta automáticamente del entorno
    embed_model = GoogleGenAIEmbedding(
        model_name=EMBED_MODEL,
        retries=10,
        retry_min_seconds=5,
        retry_max_seconds=60,
    )
    Settings.embed_model = embed_model

    # 2. Descargar datos
    records = fetch_all_records()
    log.info("Descargados %d registros de la API.", len(records))

    # 3. Construir documentos
    docs = _build_documents(records)
    conteo = Counter(d.metadata["source"] for d in docs)
    log.info("Categorias: %s", dict(conteo))

    # 4. Preflight: verificar API antes de borrar Qdrant
    _preflight_embedding_check(embed_model)

    # 5. Borrar + recrear colección (una sola vez por ciclo)
    client = get_qdrant_client()
    _drop_and_recreate(client)

    # 6. Indexar en Qdrant (los 429 se reintentan a nivel de batch)
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

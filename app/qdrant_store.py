"""
Configura el StorageContext de LlamaIndex sobre Qdrant.
- Conexión preferida por gRPC (mayor throughput).
- Colección: 3072 dims, distancia Coseno, HNSW (M=16).
"""
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, HnswConfigDiff
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import StorageContext, VectorStoreIndex

load_dotenv()

HOST = os.getenv("QDRANT_HOST", "localhost")
PORT_REST = int(os.getenv("QDRANT_PORT_REST", 6333))
PORT_GRPC = int(os.getenv("QDRANT_PORT_GRPC", 6334))
COLLECTION = os.getenv("QDRANT_COLLECTION", "trafico_valencia")

VECTOR_SIZE = 3072   # gemini-embedding-001
HNSW_M = 16


def get_qdrant_client() -> QdrantClient:
    """Devuelve un cliente Qdrant con gRPC como protocolo preferido."""
    return QdrantClient(
        host=HOST,
        grpc_port=PORT_GRPC,
        prefer_grpc=True,
    )


def ensure_collection(client: QdrantClient) -> None:
    """Crea la colección si no existe. No la sobreescribe."""
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
            hnsw_config=HnswConfigDiff(m=HNSW_M),
        )
        print(f"[qdrant_store] Colección '{COLLECTION}' creada ({VECTOR_SIZE} dims, Coseno, HNSW m={HNSW_M}).")
    else:
        print(f"[qdrant_store] Colección '{COLLECTION}' ya existe.")


def get_vector_store(client: QdrantClient) -> QdrantVectorStore:
    """Devuelve el QdrantVectorStore de LlamaIndex."""
    return QdrantVectorStore(
        collection_name=COLLECTION,
        client=client,
    )


def get_storage_context(client: QdrantClient) -> StorageContext:
    """Devuelve el StorageContext de LlamaIndex listo para indexar."""
    vector_store = get_vector_store(client)
    return StorageContext.from_defaults(vector_store=vector_store)


def get_index(client: QdrantClient) -> VectorStoreIndex:
    """Devuelve un VectorStoreIndex sobre la colección existente (sin reindexar)."""
    vector_store = get_vector_store(client)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        storage_context=storage_context,
    )

"""
Backend FastAPI — RAG Tráfico Valencia.

Endpoints:
  GET  /health   — estado del sistema y Qdrant
  POST /query    — consulta en lenguaje natural al router RAG
  POST /ingest   — dispara re-ingesta manual

Lifespan: inicializa el cliente Qdrant, el índice y el router al arrancar.
Async obligatorio: todas las rutas usan await / aquery.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.models import QueryRequest, QueryResponse, HealthResponse, IngestResponse
from app.qdrant_store import get_qdrant_client, COLLECTION
from app.router_rag import get_index, build_router, query_with_metadata
from ingesta.embedder import run_ingesta
from ingesta.scheduler import start_background_scheduler

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Estado global de la aplicación
_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y teardown de recursos al arrancar/detener la API."""
    log.info("Arrancando RAG Tráfico Valencia...")

    # Conectar Qdrant y cargar índice
    _state["qdrant_client"] = get_qdrant_client()
    _state["index"] = get_index()
    _state["router"] = build_router(_state["index"])

    # Iniciar scheduler de re-ingesta en background
    _state["scheduler"] = start_background_scheduler()

    log.info("API lista.")
    yield

    # Teardown
    _state["scheduler"].shutdown(wait=False)
    log.info("API detenida.")


app = FastAPI(
    title="RAG Tráfico Valencia",
    description="Consulta el estado del tráfico de Valencia en lenguaje natural.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Verifica el estado del sistema y la conexión con Qdrant."""
    try:
        client = _state.get("qdrant_client")
        if client is None:
            raise RuntimeError("Cliente Qdrant no inicializado.")
        info = client.get_collection(COLLECTION)
        return HealthResponse(
            status="ok",
            qdrant="conectado",
            index_points=info.points_count or 0,
        )
    except Exception as e:
        log.error("Health check fallido: %s", e)
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Consulta en lenguaje natural al router RAG.
    El router selecciona la categoría y devuelve respuesta + reason.
    """
    router = _state.get("router")
    if router is None:
        raise HTTPException(status_code=503, detail="Router no inicializado.")

    try:
        result = query_with_metadata(router, request.pregunta)
        return QueryResponse(
            respuesta=result.response,
            categoria=result.categoria,
            reason=result.reason,
        )
    except Exception as e:
        log.error("Error en /query: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest", response_model=IngestResponse)
async def ingest():
    """Dispara manualmente un ciclo completo de re-ingesta en Qdrant."""
    try:
        total = run_ingesta()
        # Recargar índice y router con los datos frescos
        _state["index"] = get_index()
        _state["router"] = build_router(_state["index"])
        return IngestResponse(status="ok", documentos=total)
    except Exception as e:
        log.error("Error en /ingest: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

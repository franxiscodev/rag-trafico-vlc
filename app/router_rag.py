"""
Router RAG — core del sistema de consultas en lenguaje natural.

Arquitectura:
- 4 QueryEngineTool filtrados por categoría (source: accesos/tuneles/avenidas/otros)
- RouterQueryEngine con PydanticSingleSelector → routing estructurado con campo 'reason'
- Fallback explícito para queries fuera del dominio de tráfico
- Async obligatorio: usar aquery() desde FastAPI
"""
import logging
from dataclasses import dataclass
from dotenv import load_dotenv

from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.selectors import PydanticSingleSelector
from llama_index.core.tools import QueryEngineTool
from llama_index.core.vector_stores.types import (
    MetadataFilters,
    ExactMatchFilter,
    FilterOperator,
)
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

from app.qdrant_store import get_qdrant_client, get_vector_store

load_dotenv()
log = logging.getLogger(__name__)

LLM_MODEL = "gemini-2.5-flash-lite"
EMBED_MODEL = "gemini-embedding-001"

# Descripciones semánticas para el selector — son el "prompt" de routing
_TOOL_DESCRIPTIONS = {
    "accesos": (
        "Úsala para consultas sobre vías rápidas y accesos a la ciudad de Valencia: "
        "autovías V-30, V-31, V-21, A-3, CV-35 y carreteras de entrada/salida. "
        "Ejemplos: '¿cómo está la V-30?', '¿hay retenciones en los accesos?', "
        "'¿puedo entrar por la V-31?'"
    ),
    "tuneles": (
        "Úsala para consultas sobre pasos inferiores y túneles de Valencia: "
        "Túnel Pérez Galdós, Germanías, Guillem de Castro, Pechina, Hermanos Machado, "
        "Av. del Cid y otros subterráneos. "
        "Ejemplos: '¿está abierto el túnel de Germanías?', '¿cómo están los pasos inferiores?'"
    ),
    "avenidas": (
        "Úsala para consultas sobre grandes avenidas y paseos urbanos de Valencia: "
        "Blasco Ibáñez, Paseo de la Alameda, Av. del Puerto, Paseo Pechina y similares. "
        "Ejemplos: '¿hay tráfico en Blasco Ibáñez?', '¿cómo está la alameda?'"
    ),
    "otros": (
        "Úsala para consultas sobre calles y tramos urbanos de Valencia no incluidos "
        "en las otras categorías: plazas, calles interiores, puentes urbanos y vías secundarias. "
        "Ejemplos: '¿cómo está el centro?', '¿hay retenciones en Colón?'"
    ),
}

_FALLBACK_DESCRIPTION = (
    "Úsala SOLO cuando la pregunta no tiene relación con el tráfico de Valencia "
    "o no puede responderse con los datos disponibles. "
    "Ejemplos: preguntas sobre el tiempo, noticias, eventos no relacionados con tráfico."
)


def _get_llm() -> GoogleGenAI:
    return GoogleGenAI(model=LLM_MODEL, temperature=0)


def _get_embed_model() -> GoogleGenAIEmbedding:
    return GoogleGenAIEmbedding(
        model_name=EMBED_MODEL,
        retries=10,
        retry_min_seconds=5,
        retry_max_seconds=60,
    )


def _make_filtered_engine(category: str, index: VectorStoreIndex, llm: GoogleGenAI):
    """Crea un query engine filtrado por categoría (metadata source)."""
    filters = MetadataFilters(
        filters=[
            ExactMatchFilter(key="source", value=category, operator=FilterOperator.EQ)
        ]
    )
    return index.as_query_engine(
        llm=llm,
        filters=filters,
        similarity_top_k=5,
    )


def _make_fallback_engine(llm: GoogleGenAI):
    """Engine de fallback — responde sin acceder a Qdrant."""
    from llama_index.core.query_engine import CustomQueryEngine
    from llama_index.core.response_synthesizers import BaseSynthesizer

    class FallbackEngine(CustomQueryEngine):
        """Devuelve siempre la respuesta de 'fuera de dominio'."""
        def custom_query(self, query_str: str) -> str:
            return (
                "Lo siento, no tengo información sobre eso. "
                "Solo puedo responder preguntas sobre el estado del tráfico "
                "en Valencia en tiempo real."
            )

    return FallbackEngine()


def build_router(index: VectorStoreIndex) -> RouterQueryEngine:
    """
    Construye el RouterQueryEngine con las 4 herramientas + fallback.
    El selector PydanticSingleSelector devuelve el campo 'reason' obligatorio
    para trazabilidad.
    """
    llm = _get_llm()

    tools = [
        QueryEngineTool.from_defaults(
            query_engine=_make_filtered_engine(cat, index, llm),
            name=cat,
            description=desc,
        )
        for cat, desc in _TOOL_DESCRIPTIONS.items()
    ]

    fallback_tool = QueryEngineTool.from_defaults(
        query_engine=_make_fallback_engine(llm),
        name="sin_informacion",
        description=_FALLBACK_DESCRIPTION,
    )
    tools.append(fallback_tool)

    router = RouterQueryEngine(
        selector=PydanticSingleSelector.from_defaults(llm=llm),
        query_engine_tools=tools,
        verbose=True,
    )

    log.info("RouterQueryEngine construido con %d herramientas.", len(tools))
    return router


@dataclass
class RouterResult:
    response: str
    categoria: str
    reason: str


def query_with_metadata(router: RouterQueryEngine, query_str: str) -> RouterResult:
    """
    Ejecuta una consulta contra el router y devuelve respuesta + categoría + reason.
    Llama al selector directamente para capturar la selección antes de ejecutar el engine.
    """
    from llama_index.core.schema import QueryBundle

    query_bundle = QueryBundle(query_str)
    selection = router._selector.select(router._metadatas, query_bundle)
    engine = router._query_engines[selection.ind]
    categoria = router._metadatas[selection.ind].name
    response = engine.query(query_str)

    return RouterResult(
        response=str(response),
        categoria=categoria,
        reason=selection.reason,
    )


def get_index() -> VectorStoreIndex:
    """Carga el índice existente en Qdrant sin re-indexar."""
    from app.qdrant_store import get_index as _get_index
    # Configurar embed_model antes de construir el índice
    Settings.embed_model = _get_embed_model()
    Settings.llm = _get_llm()
    client = get_qdrant_client()
    return _get_index(client)

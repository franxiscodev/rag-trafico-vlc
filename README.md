# RAG Tráfico Valencia

Sistema RAG (*Retrieval-Augmented Generation*) end-to-end para consultar el estado del tráfico de Valencia en tiempo real usando lenguaje natural. Proyecto académico de evaluación final del Master en IA, Cloud Computing & DevOps — Pontia.

---

## Descripción

El sistema descarga cada 3 minutos los 382 tramos de la API Open Data Valencia, genera embeddings con Gemini y los almacena en Qdrant. Las consultas en lenguaje natural son enrutadas por categoría (accesos, túneles, avenidas, otros) mediante un `RouterQueryEngine` de LlamaIndex, que recupera los tramos relevantes y genera una respuesta con el LLM.

Incluye fallback automático a OpenRouter (Llama 3.2) cuando Gemini devuelve error 429 por cuota agotada.

---

## Requisitos previos

| Herramienta | Versión mínima | Uso |
|-------------|---------------|-----|
| Python | 3.11 | Entorno de ejecución |
| [UV](https://docs.astral.sh/uv/) | 0.4+ | Gestión de entorno y dependencias |
| Docker Desktop | 4.x | Ejecutar Qdrant en contenedor |

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd rag-trafico-vlc

# 2. Instalar dependencias con UV
uv sync

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env y añadir las API keys necesarias
```

---

## Levantar Qdrant

```bash
docker compose up -d
```

Qdrant quedará disponible en `http://localhost:6333` (REST) y `localhost:6334` (gRPC).
Panel de administración: `http://localhost:6333/dashboard`

---

## Ejecutar ingesta

Descarga los datos de tráfico, genera embeddings y los indexa en Qdrant:

```bash
uv run python -m ingesta.embedder
```

La ingesta borra y recrea la colección completa en cada ciclo. Incluye un *preflight check* que aborta antes de tocar Qdrant si la API de embedding devuelve 429.

---

## Arrancar la API

```bash
uv run uvicorn app.main:app --port 8001
```

El scheduler de re-ingesta arranca automáticamente en background cada 3 minutos (configurable con `SCHEDULER_ENABLED`).

Documentación interactiva disponible en `http://localhost:8001/docs`.

---

## Endpoints disponibles

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Estado del sistema y conexión con Qdrant |
| `POST` | `/query` | Consulta en lenguaje natural al router RAG |
| `POST` | `/ingest` | Dispara un ciclo de re-ingesta manual |

### Ejemplo — POST /query

```bash
curl -X POST http://localhost:8001/query \
     -H "Content-Type: application/json" \
     -d '{"pregunta": "¿Cómo está el túnel de Pérez Galdós?"}'
```

Respuesta:

```json
{
  "respuesta": "El túnel Pérez Galdós tiene tráfico fluido en este momento.",
  "categoria": "tuneles",
  "reason": "La pregunta menciona explícitamente un túnel de Valencia."
}
```

---

## Ejecutar tests

```bash
uv run pytest tests/ -v
```

Los tests usan mocks para no consumir cuota de las APIs externas ni requerir Qdrant activo. Ver `tests/test_api.py` para detalles de la estrategia de mockeo.

---

## Variables de entorno

Copiar `.env.example` a `.env` y completar los valores:

| Variable | Requerida | Valor por defecto | Descripción |
|----------|-----------|-------------------|-------------|
| `GOOGLE_API_KEY` | Sí | — | Clave de la API de Google AI (Gemini embeddings + LLM) |
| `OPENROUTER_API_KEY` | No | — | Clave de OpenRouter para el LLM de fallback ante error 429 |
| `SCHEDULER_ENABLED` | No | `true` | Activa el scheduler de re-ingesta automática cada 3 minutos |
| `FORCE_OPENROUTER` | No | `false` | Fuerza el uso de OpenRouter como LLM primario (útil para demos sin cuota Gemini) |
| `QDRANT_HOST` | No | `localhost` | Host donde corre Qdrant |
| `QDRANT_PORT_REST` | No | `6333` | Puerto REST de Qdrant |
| `QDRANT_PORT_GRPC` | No | `6334` | Puerto gRPC de Qdrant |
| `QDRANT_COLLECTION` | No | `trafico_valencia` | Nombre de la colección en Qdrant |

---

## Stack tecnológico

| Capa | Tecnología | Detalle |
|------|-----------|---------|
| Lenguaje | Python 3.11 | Gestionado con UV |
| Framework RAG | LlamaIndex | `RouterQueryEngine` + `StorageContext` |
| Vector DB | Qdrant | Docker, REST 6333 / gRPC 6334 |
| Embeddings | `gemini-embedding-001` | 3072 dims, distancia Coseno, HNSW m=16 |
| LLM primario | `gemini-2.5-flash-lite` | Temperatura 0, via `llama-index-llms-google-genai` |
| LLM fallback | `meta-llama/llama-3.2-3b-instruct:free` | OpenRouter, activado por 429 o `FORCE_OPENROUTER=true` |
| Routing | `PydanticSingleSelector` / `LLMSingleSelector` | Selección estructurada con campo `reason` |
| Backend | FastAPI | Lifespan async, endpoints `/health` `/query` `/ingest` |
| Reintentos | Tenacity | Fallback OpenRouter ante `ResourceExhausted` |
| Scheduler | APScheduler | Re-ingesta automática cada 3 minutos |
| Fuente de datos | Open Data Valencia | 382 tramos, actualización cada 3 min |

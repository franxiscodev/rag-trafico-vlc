# RAG Tráfico Valencia — Contexto para Claude Code

## 🎯 Proyecto
Sistema RAG End-to-End para consultar el estado del tráfico de Valencia en tiempo real usando lenguaje natural. Proyecto académico de evaluación final del Master en IA, Cloud Computing & DevOps.

## 🧰 Stack Tecnológico
| Capa | Tecnología |
|------|-----------|
| Lenguaje | Python (UV para gestión de entorno) |
| Framework RAG | LlamaIndex (RouterQueryEngine + StorageContext) |
| Vector DB | Qdrant en Docker (REST: 6333, gRPC: 6334) |
| Embedding | Gemini Embedding 001 — 3072 dims, distancia Coseno |
| LLM | Gemini 1.5 Flash — temperatura 0 |
| Backend | FastAPI con lifespan async |
| OS | Windows 11 |
| Editor | VS Code |

## 🗂️ Estructura del Proyecto
```
rag-trafico-valencia/
├── .env.example
├── .gitignore
├── CLAUDE.md                 ← este archivo
├── README.md
├── docker-compose.yml        # Qdrant
├── pyproject.toml            # UV + dependencias
├── app/
│   ├── main.py               # FastAPI + lifespan
│   ├── router_rag.py         # RouterQueryEngine
│   ├── qdrant_store.py       # StorageContext
│   └── models.py             # Schemas Pydantic
├── ingesta/
│   ├── api_client.py         # API Open Data Valencia
│   ├── categorizer.py        # Clasificación tramos
│   ├── embedder.py           # Gemini Embedding
│   └── scheduler.py          # Actualización cada 3 min
├── notebooks/
│   └── test_router.ipynb
├── tests/
│   └── test_api.py
└── docs/
    └── resultados_tests.md
```

## 📡 Fuente de Datos
- **API**: Open Data Valencia — Tráfico Tiempo Real
- **URL base**: `https://valencia.opendatasoft.com/api/explore/v2.1/catalog/datasets/estat-transit-temps-real-estado-trafico-tiempo-real/records`
- **Registros**: 382 tramos
- **Frecuencia de actualización**: cada 3 minutos
- **Estrategia de ingesta**: borrado + recreación completa de la colección Qdrant en cada ciclo

## 🗃️ Categorías de Routing (metadata `source`)
| Categoría | Descripción | Ejemplo |
|-----------|-------------|---------|
| `accesos` | Vías de acceso a la ciudad | V-31, V-30 |
| `tuneles` | Pasos subterráneos | Túnel Pérez Galdós, Germanías |
| `avenidas` | Grandes avenidas urbanas | Blasco Ibáñez |
| `otros` | Tramos sin categoría específica | — |

## 🔢 Códigos de Estado del Tráfico
| Código | Significado |
|--------|-------------|
| 0 | Fluido |
| 1 | Denso |
| 2 | Congestionado |
| 3 | Cortado |
| 4 / 9 | Sin datos |
| 5 | Paso inferior — Fluido |
| 6 | Paso inferior — Denso |
| 7 | Paso inferior — Congestionado |
| 8 | Paso inferior — Cortado |

## 🌿 Ramas Git del Proyecto
```
main
├── feature/infraestructura   ← Qdrant + Docker
├── feature/ingesta           ← API client + embeddings
├── feature/router-rag        ← RouterQueryEngine
├── feature/api               ← FastAPI endpoints
├── feature/testing           ← Tests integración
└── feature/documentacion     ← README + entrega PDF
```

## ⚙️ Reglas de Trabajo
- Responde **siempre en español**, preservando términos técnicos en inglés
- **Nunca `git add .`** — añadir archivos explícitamente uno a uno
- **Nunca subir `.env`** — verificar `.gitignore` antes de cualquier commit
- Crear rama antes de implementar cualquier feature
- Guardar planes y documentación de diseño en `plan/` (excluido del repo)
- Implementar **paso a paso**, esperando confirmación antes de avanzar
- Para lógica nueva, validar primero en Jupyter antes de migrar a producción

## 🚨 Consideraciones Críticas
- **Error 429 Gemini**: implementar `tenacity` para reintentos + Open Router como fallback
- **Async obligatorio**: todo el stack FastAPI usa `aquery` (no `query` síncrono)
- **gRPC preferido** sobre REST para conexión Qdrant (throughput)
- **PydanticSingleSelector** para output estructurado del router con campo `reason`
- El campo `reason` del router es obligatorio para trazabilidad/observabilidad

## 📦 Dependencias Clave (pyproject.toml)
```toml
dependencies = [
    "fastapi",
    "uvicorn",
    "llama-index",
    "llama-index-vector-stores-qdrant",
    "llama-index-llms-gemini",
    "llama-index-embeddings-gemini",
    "qdrant-client",
    "google-generativeai",
    "tenacity",
    "apscheduler",
    "httpx",
    "python-dotenv",
    "pydantic",
]
```

## 🗺️ Plan de Trabajo
El proyecto sigue un plan de 6 fases documentado en `plan/PLAN_RAG_Valencia.md`.
- Antes de implementar cualquier feature, consulta ese archivo para entender el contexto de la fase actual, sus entregables esperados y las tareas pendientes.
- Si una tarea es ambigua o hay decisiones de diseño no cubiertas en este `CLAUDE.md`, busca orientación en los `.md` de la carpeta `plan/`.
- El plan es la fuente de verdad sobre el **qué**. Este `CLAUDE.md` es la fuente de verdad sobre el **cómo**.

## 🔑 Variables de Entorno (.env)
```
GEMINI_API_KEY=
QDRANT_HOST=localhost
QDRANT_PORT_REST=6333
QDRANT_PORT_GRPC=6334
QDRANT_COLLECTION=trafico_valencia
```

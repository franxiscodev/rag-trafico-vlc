# Resultados de Tests — RAG Tráfico Valencia

## Entorno de ejecución

| Parámetro | Valor |
|-----------|-------|
| Fecha | 2026-03-22 |
| Python | 3.12.10 |
| pytest | 9.0.2 |
| Modo | Mock (sin llamadas a Gemini ni Qdrant) |
| Comando | `uv run pytest tests/test_api.py -v` |

---

## Resultados — 14/14 tests pasados

### /health (2 tests)

| Test | Resultado |
|------|-----------|
| Estado OK con Qdrant conectado y 382 vectores | PASSED |
| Retorna 503 cuando Qdrant no está disponible | PASSED |

### /query — Routing por categoría (7 tests)

| Pregunta | Categoría esperada | Resultado |
|----------|--------------------|-----------|
| ¿Cómo está el túnel de Pérez Galdós? | `tuneles` | PASSED |
| ¿Hay retenciones en la V-31? | `accesos` | PASSED |
| ¿Cómo está Blasco Ibáñez? | `avenidas` | PASSED |
| ¿Cómo está el centro? | `otros` | PASSED |
| ¿Cuál es el mejor restaurante de Valencia? | `sin_informacion` | PASSED |
| Respuesta incluye campo `reason` no vacío | — | PASSED |
| Retorna 503 si el router no está inicializado | — | PASSED |

### /query — Fallback (1 test)

| Test | Resultado |
|------|-----------|
| Query fuera de dominio → categoría `sin_informacion` | PASSED |

### /ingest (2 tests)

| Test | Resultado |
|------|-----------|
| Re-ingesta exitosa devuelve `{"status":"ok","documentos":382}` | PASSED |
| Error en ingesta devuelve 500 | PASSED |

---

## Latencia (modo mock, 20 iteraciones, umbral < 100 ms)

| Endpoint | Promedio | p95 | Umbral | Resultado |
|----------|----------|-----|--------|-----------|
| `POST /query` | 1.2 ms | 3.1 ms | 100 ms | PASSED |
| `GET /health` | 1.2 ms | — | 50 ms | PASSED |

> **Nota:** Los valores de latencia corresponden al overhead de FastAPI + mock puro,
> sin incluir el tiempo real de llamadas a Gemini (~1-3 s) ni a Qdrant (~5-20 ms).
> En producción la latencia dominante será la del LLM.

---

## Cobertura de escenarios

| Escenario | Cubierto |
|-----------|----------|
| Routing correcto por las 4 categorías + fallback | ✓ |
| Campo `reason` presente en todas las respuestas | ✓ |
| Manejo de errores 503 (Qdrant caído / router no init) | ✓ |
| Manejo de errores 500 (fallo en ingesta) | ✓ |
| Latencia endpoint query (mock) < 100 ms | ✓ |
| Latencia endpoint health < 50 ms | ✓ |
| Tests sin consumir cuota API (patrón mock) | ✓ |

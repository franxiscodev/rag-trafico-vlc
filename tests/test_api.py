"""
Tests de integración para la API FastAPI — RAG Tráfico Valencia.

Estrategia mock (sin cuota Gemini, sin Qdrant):
- El lifespan se parchea para no conectar a Qdrant ni inicializar el LLM.
- _state se puebla con objetos mock antes de cada test.
- query_with_metadata se sustituye por una función que devuelve RouterResult fijos.
- run_ingesta se parchea para devolver un conteo ficticio.

Ejecutar: uv run pytest tests/test_api.py -v
"""
import time
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app, _state
from app.router_rag import RouterResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_qdrant_client(points: int = 382):
    client = MagicMock()
    client.get_collection.return_value.points_count = points
    return client


def _make_mock_router():
    """Router ficticio; query_with_metadata se parchea aparte."""
    return MagicMock()


MOCK_RESULTS = {
    "tuneles": RouterResult(
        response="El túnel Pérez Galdós tiene tráfico fluido.",
        categoria="tuneles",
        reason="La pregunta menciona un túnel de Valencia.",
    ),
    "accesos": RouterResult(
        response="La V-31 está fluida, sin retenciones.",
        categoria="accesos",
        reason="La pregunta hace referencia a una vía rápida de acceso.",
    ),
    "avenidas": RouterResult(
        response="Blasco Ibáñez presenta tráfico denso.",
        categoria="avenidas",
        reason="La pregunta menciona una gran avenida urbana.",
    ),
    "otros": RouterResult(
        response="El centro de Valencia tiene tráfico fluido.",
        categoria="otros",
        reason="Tramo urbano sin categoría específica.",
    ),
    "sin_informacion": RouterResult(
        response="Lo siento, solo respondo sobre tráfico de Valencia.",
        categoria="sin_informacion",
        reason="La pregunta no tiene relación con el tráfico.",
    ),
}


@pytest.fixture(autouse=True)
def mock_app_state():
    """Inyecta estado mock en la app antes de cada test y lo limpia después."""
    _state["qdrant_client"] = _make_mock_qdrant_client()
    _state["index"] = MagicMock()
    _state["router"] = _make_mock_router()
    _state["scheduler"] = MagicMock()
    yield
    _state.clear()


@pytest.fixture
def client():
    """TestClient con lifespan desactivado (lo gestionamos con mock_app_state)."""
    with patch("app.main.get_qdrant_client", return_value=_make_mock_qdrant_client()), \
         patch("app.main.get_index", return_value=MagicMock()), \
         patch("app.main.build_router", return_value=MagicMock()), \
         patch("app.main.start_background_scheduler", return_value=MagicMock()):
        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# Tests — /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["qdrant"] == "conectado"
        assert data["index_points"] == 382

    def test_health_qdrant_caido(self, client):
        _state["qdrant_client"].get_collection.side_effect = ConnectionError("Qdrant no disponible")
        resp = client.get("/health")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Tests — /query (routing por categoría + fallback)
# ---------------------------------------------------------------------------

class TestQuery:
    @pytest.mark.parametrize("pregunta,categoria_esperada", [
        ("¿Cómo está el túnel de Pérez Galdós?", "tuneles"),
        ("¿Hay retenciones en la V-31?", "accesos"),
        ("¿Cómo está Blasco Ibáñez?", "avenidas"),
        ("¿Cómo está el centro?", "otros"),
        ("¿Cuál es el mejor restaurante de Valencia?", "sin_informacion"),
    ])
    def test_routing_categoria(self, client, pregunta, categoria_esperada):
        resultado_mock = MOCK_RESULTS[categoria_esperada]
        with patch("app.main.query_with_metadata", return_value=resultado_mock):
            resp = client.post("/query", json={"pregunta": pregunta})
        assert resp.status_code == 200
        data = resp.json()
        assert data["categoria"] == categoria_esperada
        assert data["respuesta"]
        assert data["reason"]

    def test_query_incluye_reason(self, client):
        with patch("app.main.query_with_metadata", return_value=MOCK_RESULTS["tuneles"]):
            resp = client.post("/query", json={"pregunta": "¿Cómo está el túnel?"})
        assert resp.status_code == 200
        assert "reason" in resp.json()
        assert resp.json()["reason"] != ""

    def test_fallback_fuera_de_dominio(self, client):
        with patch("app.main.query_with_metadata", return_value=MOCK_RESULTS["sin_informacion"]):
            resp = client.post("/query", json={"pregunta": "¿Cuántos goles marcó Messi?"})
        assert resp.status_code == 200
        assert resp.json()["categoria"] == "sin_informacion"

    def test_query_error_router_no_inicializado(self, client):
        _state.pop("router", None)
        resp = client.post("/query", json={"pregunta": "¿Cómo está la V-30?"})
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Tests — /ingest
# ---------------------------------------------------------------------------

class TestIngest:
    def test_ingest_ok(self, client):
        with patch("app.main.run_ingesta", return_value=382), \
             patch("app.main.get_index", return_value=MagicMock()), \
             patch("app.main.build_router", return_value=MagicMock()):
            resp = client.post("/ingest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["documentos"] == 382

    def test_ingest_error(self, client):
        with patch("app.main.run_ingesta", side_effect=RuntimeError("Fallo de red")):
            resp = client.post("/ingest")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Test de latencia — mock vs overhead de la API
# ---------------------------------------------------------------------------

class TestLatencia:
    N = 20  # iteraciones para estabilizar la medición

    def test_latencia_query_mock(self, client):
        """El endpoint /query con mock debe responder en < 100 ms."""
        with patch("app.main.query_with_metadata", return_value=MOCK_RESULTS["accesos"]):
            tiempos = []
            for _ in range(self.N):
                t0 = time.perf_counter()
                resp = client.post("/query", json={"pregunta": "¿Cómo está la V-30?"})
                tiempos.append(time.perf_counter() - t0)
            assert resp.status_code == 200

        promedio_ms = (sum(tiempos) / len(tiempos)) * 1000
        p95_ms = sorted(tiempos)[int(self.N * 0.95)] * 1000
        print(f"\n  Latencia /query (mock) — promedio: {promedio_ms:.1f} ms | p95: {p95_ms:.1f} ms")
        assert promedio_ms < 100, f"Latencia media {promedio_ms:.1f} ms supera el umbral de 100 ms"

    def test_latencia_health(self, client):
        """GET /health debe responder en < 50 ms."""
        tiempos = []
        for _ in range(self.N):
            t0 = time.perf_counter()
            resp = client.get("/health")
            tiempos.append(time.perf_counter() - t0)
        assert resp.status_code == 200

        promedio_ms = (sum(tiempos) / len(tiempos)) * 1000
        print(f"\n  Latencia /health — promedio: {promedio_ms:.1f} ms")
        assert promedio_ms < 50, f"Latencia media {promedio_ms:.1f} ms supera el umbral de 50 ms"

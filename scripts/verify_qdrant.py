"""
Verifica la conexión con Qdrant por REST y gRPC.
Uso: uv run python scripts/verify_qdrant.py
"""
import os
import sys
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

load_dotenv()

HOST = os.getenv("QDRANT_HOST", "localhost")
PORT_REST = int(os.getenv("QDRANT_PORT_REST", 6333))
PORT_GRPC = int(os.getenv("QDRANT_PORT_GRPC", 6334))


def check_rest() -> bool:
    print(f"[REST]  Conectando a {HOST}:{PORT_REST} ...")
    try:
        client = QdrantClient(host=HOST, port=PORT_REST)
        info = client.get_collections()
        print(f"[REST]  OK — colecciones: {[c.name for c in info.collections]}")
        return True
    except Exception as e:
        print(f"[REST]  ERROR: {e}")
        return False


def check_grpc() -> bool:
    print(f"[gRPC]  Conectando a {HOST}:{PORT_GRPC} ...")
    try:
        client = QdrantClient(host=HOST, grpc_port=PORT_GRPC, prefer_grpc=True)
        info = client.get_collections()
        print(f"[gRPC]  OK — colecciones: {[c.name for c in info.collections]}")
        return True
    except Exception as e:
        print(f"[gRPC]  ERROR: {e}")
        return False


if __name__ == "__main__":
    ok_rest = check_rest()
    ok_grpc = check_grpc()

    if ok_rest and ok_grpc:
        print("\n[OK] Qdrant accesible por REST y gRPC.")
        sys.exit(0)
    else:
        print("\n[FALLO] Error en la conexion con Qdrant. Esta corriendo `docker compose up -d`?")
        sys.exit(1)

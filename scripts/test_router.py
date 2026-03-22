"""
Valida el RouterQueryEngine con 5 consultas representativas.
Muestra para cada una: respuesta, categoría elegida y campo reason.

Uso: uv run python scripts/test_router.py
Requisitos: Qdrant corriendo + .env con GOOGLE_API_KEY + índice poblado
"""
from dotenv import load_dotenv
load_dotenv()

from app.router_rag import get_index, build_router, query_with_metadata

CONSULTAS = [
    "¿Cómo está el túnel de Pérez Galdós?",
    "¿Hay retenciones en la V-31?",
    "¿Cómo está Blasco Ibáñez ahora mismo?",
    "¿Cuál es el mejor restaurante de Valencia?",
    "¿Está cortado algún acceso por la V-30?",
]

SEPARADOR = "-" * 60


def main():
    print("Cargando índice desde Qdrant...")
    index = get_index()
    print("Construyendo router...\n")
    router = build_router(index)

    for i, pregunta in enumerate(CONSULTAS, 1):
        print(SEPARADOR)
        print(f"[{i}] {pregunta}")
        result = query_with_metadata(router, pregunta)
        print(f"  Categoria : {result.categoria}")
        print(f"  Reason    : {result.reason}")
        print(f"  Respuesta : {result.response}")
        print()

    print(SEPARADOR)
    print(f"Test completado: {len(CONSULTAS)}/{len(CONSULTAS)} consultas procesadas.")


if __name__ == "__main__":
    main()

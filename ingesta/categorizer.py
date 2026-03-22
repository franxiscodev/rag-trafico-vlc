"""
Clasifica cada tramo en una de las 4 categorías de routing.

Prioridad de detección (de más a menos específica):
  1. tuneles  — pasos inferiores / subterráneos
  2. accesos  — vías rápidas de acceso a la ciudad (V-30, V-31, A-3…)
  3. avenidas — grandes avenidas y paseos urbanos
  4. otros    — cualquier tramo sin categoría específica
"""
import re
from typing import Any

# Patrones por categoría (se aplican sobre el nombre en mayúsculas)
_TUNELES = [
    "PASO INFERIOR",
    "PAS INFERIOR",
    "TUNEL",
    "TUNNEL",
]

_ACCESOS = [
    r"\bV-30\b",
    r"\bV-31\b",
    r"\bV-21\b",
    r"\bA-3\b",
    r"\bCV-\d+",
    r"\bAP-\d+",
    "PASO ELEVADO",
    "ACCESO",
]

_AVENIDAS = [
    r"\bAV\.",
    r"\bAVDA\b",
    "AVENIDA",
    "PASEO",
    "PASSEIG",
    "ALAMEDA",
    "BLASCO IBA",   # Blasco Ibáñez (normalizado)
    "BULEVARD",
    "BOULEVARD",
]

_ESTADOS: dict[int | None, str] = {
    0: "Fluido",
    1: "Denso",
    2: "Congestionado",
    3: "Cortado",
    4: "Sin datos",
    5: "Paso inferior - Fluido",
    6: "Paso inferior - Denso",
    7: "Paso inferior - Congestionado",
    8: "Paso inferior - Cortado",
    9: "Sin datos",
    None: "Sin datos",
}


def _matches(text: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if re.search(pat, text):
            return True
    return False


def categorize(nombre: str | None) -> str:
    """Devuelve la categoría ('tuneles', 'accesos', 'avenidas', 'otros')."""
    if not nombre:
        return "otros"
    upper = nombre.upper()

    if _matches(upper, _TUNELES):
        return "tuneles"
    if _matches(upper, _ACCESOS):
        return "accesos"
    if _matches(upper, _AVENIDAS):
        return "avenidas"
    return "otros"


def estado_texto(codigo: int | None) -> str:
    """Convierte el código numérico de estado en texto legible."""
    return _ESTADOS.get(codigo, "Sin datos")


def build_document_text(record: dict[str, Any]) -> str:
    """
    Construye el texto que se embedderá para un tramo.
    Formato rico en información para mejorar la recuperación semántica.
    """
    nombre = record.get("denominacion") or "Tramo sin nombre"
    estado_cod = record.get("estado")
    estado = estado_texto(estado_cod)
    idtramo = record.get("idtramo", "?")
    categoria = categorize(nombre)

    geo = record.get("geo_point_2d") or {}
    lat = geo.get("lat", "")
    lon = geo.get("lon", "")
    coords = f"({lat:.5f}, {lon:.5f})" if lat and lon else ""

    return (
        f"Tramo: {nombre}\n"
        f"Estado del tráfico: {estado}\n"
        f"Categoría: {categoria}\n"
        f"ID tramo: {idtramo}\n"
        f"Coordenadas: {coords}"
    )

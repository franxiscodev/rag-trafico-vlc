"""
Cliente para la API Open Data Valencia — Tráfico Tiempo Real.
Descarga los 382 tramos con paginación automática.
"""
import httpx
from typing import Any

API_URL = (
    "https://valencia.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
    "estat-transit-temps-real-estado-trafico-tiempo-real/records"
)
PAGE_SIZE = 100


def fetch_all_records() -> list[dict[str, Any]]:
    """Descarga todos los tramos de tráfico de Valencia."""
    records: list[dict[str, Any]] = []
    offset = 0

    with httpx.Client(timeout=20) as client:
        while True:
            response = client.get(API_URL, params={"limit": PAGE_SIZE, "offset": offset})
            response.raise_for_status()
            data = response.json()
            page = data.get("results", [])
            if not page:
                break
            records.extend(page)
            offset += len(page)
            if offset >= data.get("total_count", 0):
                break

    return records

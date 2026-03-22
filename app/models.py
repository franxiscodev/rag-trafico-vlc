"""Schemas Pydantic para los endpoints de la API."""
from pydantic import BaseModel


class QueryRequest(BaseModel):
    pregunta: str


class QueryResponse(BaseModel):
    respuesta: str
    categoria: str
    reason: str


class HealthResponse(BaseModel):
    status: str
    qdrant: str
    index_points: int


class IngestResponse(BaseModel):
    status: str
    documentos: int

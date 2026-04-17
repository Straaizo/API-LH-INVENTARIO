from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None


# Respuestas de error estándar para documentar en los decoradores
RESP_400 = {400: {"description": "Datos inválidos o faltantes en la solicitud"}}
RESP_401 = {401: {"description": "Token JWT ausente, inválido o expirado"}}
RESP_404 = {404: {"description": "Recurso no encontrado"}}
RESP_409 = {409: {"description": "Conflicto: el recurso ya existe"}}
RESP_500 = {500: {"description": "Error interno del servidor"}}

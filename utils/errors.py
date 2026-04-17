"""
Respuestas de error sanitizadas.
Loguea el error real internamente y devuelve un mensaje genérico al cliente.
"""

import logging
from fastapi.responses import JSONResponse

_log = logging.getLogger(__name__)


def server_error(e: Exception, ctx: str = "") -> JSONResponse:
    """Loguea el error completo y retorna 500 con mensaje genérico."""
    label = f"[{ctx}] " if ctx else ""
    _log.error("%s%s: %s", label, type(e).__name__, e, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor"},
    )

"""
audit_log.py — Middleware de auditoría.
Registra cada request: método, ruta, usuario, IP, status y duración.
"""
import logging
import time

from fastapi import Request
from jose import jwt, JWTError

from config import Config

logger = logging.getLogger("audit")

_SKIP = {"/api/", "/"}


async def audit_middleware(request: Request, call_next):
    start = time.time()

    user_id = "-"
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(auth[7:], Config.JWT_SECRET_KEY, algorithms=["HS256"])
            raw = payload.get("sub", "-")
            user_id = str(raw)[:8]
        except JWTError:
            pass

    ip = request.headers.get("X-Forwarded-For", "")
    ip = ip.split(",")[0].strip() if ip else (request.client.host if request.client else "-")

    response = await call_next(request)

    ms = int((time.time() - start) * 1000)

    if request.url.path not in _SKIP:
        logger.info(
            "[AUDIT] %s %s | user:%s | ip:%s | %d | %dms",
            request.method,
            request.url.path,
            user_id,
            ip,
            response.status_code,
            ms,
        )

    return response

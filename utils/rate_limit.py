"""
Rate limiting por IP — protección contra fuerza bruta en login.
Bloquea la IP tras MAX_ATTEMPTS intentos fallidos en WINDOW_SECONDS segundos.

Whitelist: definir RATE_LIMIT_WHITELIST en .env con IPs separadas por coma.
           Usar * para saltear completamente en modo DEBUG.
"""
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)

MAX_ATTEMPTS   = 5
WINDOW_SECONDS = 900
BLOCK_SECONDS  = 1800

_DEBUG: bool = os.getenv("DEBUG", "True") == "True"

# IPs que nunca se bloquean. "*" = todas (útil en DEBUG/testing)
_WHITELIST: set[str] = {
    ip.strip()
    for ip in os.getenv("RATE_LIMIT_WHITELIST", "").split(",")
    if ip.strip()
}


@dataclass
class _State:
    attempts:      int   = 0
    window_start:  float = field(default_factory=time.time)
    blocked_until: float = 0.0


_store: dict[str, _State] = defaultdict(_State)
_lock  = Lock()


def _real_ip(request) -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.client and request.client.host) or "unknown"


def _is_whitelisted(ip: str) -> bool:
    if "*" in _WHITELIST:
        return True
    return ip in _WHITELIST


def is_blocked(request) -> tuple[bool, str]:
    ip  = _real_ip(request)
    if _is_whitelisted(ip):
        return False, ip
    now = time.time()
    with _lock:
        st = _store[ip]
        if st.blocked_until > now:
            secs = int(st.blocked_until - now)
            logger.warning("[RATE-LIMIT] IP bloqueada: %s | %ds restantes", ip, secs)
            return True, ip
        if now - st.window_start > WINDOW_SECONDS:
            st.attempts      = 0
            st.window_start  = now
            st.blocked_until = 0.0
        return False, ip


def record_failure(request) -> bool:
    ip  = _real_ip(request)
    if _is_whitelisted(ip):
        return False
    now = time.time()
    with _lock:
        st = _store[ip]
        if now - st.window_start > WINDOW_SECONDS:
            st.attempts     = 0
            st.window_start = now
        st.attempts += 1
        if st.attempts >= MAX_ATTEMPTS:
            st.blocked_until = now + BLOCK_SECONDS
            logger.warning(
                "[RATE-LIMIT] IP BLOQUEADA — %d intentos: %s | hasta %s UTC",
                st.attempts, ip,
                time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(st.blocked_until)),
            )
            return True
        logger.warning("[RATE-LIMIT] Login fallido %d/%d — IP: %s", st.attempts, MAX_ATTEMPTS, ip)
        return False


def record_success(request) -> None:
    ip = _real_ip(request)
    with _lock:
        if ip in _store:
            _store[ip].attempts      = 0
            _store[ip].blocked_until = 0.0
    logger.info("[RATE-LIMIT] Login exitoso — contador limpiado para IP: %s", ip)

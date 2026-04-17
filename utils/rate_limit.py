"""
Rate limiting por IP — protección contra fuerza bruta.
Bloquea la IP tras MAX_ATTEMPTS intentos fallidos en WINDOW_SECONDS segundos.
Todos los eventos quedan registrados en el log del servidor.
"""
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)

MAX_ATTEMPTS   = 5      # intentos fallidos antes de bloquear
WINDOW_SECONDS = 900    # 15 min — ventana de conteo
BLOCK_SECONDS  = 1800   # 30 min — duración del bloqueo


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


def is_blocked(request) -> tuple[bool, str]:
    """Retorna (bloqueado, ip). Loguea si la IP está bloqueada."""
    ip  = _real_ip(request)
    now = time.time()
    with _lock:
        st = _store[ip]
        if st.blocked_until > now:
            secs = int(st.blocked_until - now)
            logger.warning(
                "[RATE-LIMIT] Acceso denegado — IP bloqueada: %s | %ds restantes", ip, secs
            )
            return True, ip
        if now - st.window_start > WINDOW_SECONDS:
            st.attempts      = 0
            st.window_start  = now
            st.blocked_until = 0.0
        return False, ip


def record_failure(request) -> bool:
    """Registra intento fallido. Retorna True si la IP queda bloqueada ahora."""
    ip  = _real_ip(request)
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
                "[RATE-LIMIT] IP BLOQUEADA — %d intentos fallidos: %s | bloqueada hasta %s UTC",
                st.attempts, ip,
                time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(st.blocked_until)),
            )
            return True
        logger.warning(
            "[RATE-LIMIT] Login fallido %d/%d — IP: %s", st.attempts, MAX_ATTEMPTS, ip
        )
        return False


def record_success(request) -> None:
    """Limpia el contador tras autenticación exitosa."""
    ip = _real_ip(request)
    with _lock:
        if ip in _store:
            _store[ip].attempts      = 0
            _store[ip].blocked_until = 0.0
    logger.info("[RATE-LIMIT] Login exitoso — contador limpiado para IP: %s", ip)

"""
global_rate_limit.py — Rate limiting global para todos los endpoints.

Lógica:
  - MAX_REQUESTS en WINDOW_SECONDS → bloqueo temporal de BLOCK_SECONDS
  - Tras MAX_BLOCKS bloqueos acumulados → blacklist permanente
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)

MAX_REQUESTS   = 60     # peticiones permitidas por ventana
WINDOW_SECONDS = 60     # ventana de conteo (1 minuto)
BLOCK_SECONDS  = 1800   # duración del bloqueo (30 min)
MAX_BLOCKS     = 3      # bloqueos antes de blacklist permanente


@dataclass
class _State:
    requests:     int   = 0
    window_start: float = field(default_factory=time.time)
    blocked_until: float = 0.0
    block_count:  int   = 0
    blacklisted:  bool  = False


_store: dict[str, _State] = defaultdict(_State)
_lock  = Lock()


def _get_ip(request) -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.client and request.client.host) or "unknown"


def check_and_record(request) -> tuple[bool, str]:
    """
    Verifica y registra la petición.
    Retorna (bloqueado, ip).
    """
    ip  = _get_ip(request)
    now = time.time()

    with _lock:
        st = _store[ip]

        # Blacklist permanente
        if st.blacklisted:
            logger.warning("[GLOBAL-RL] BLACKLIST PERMANENTE — IP: %s", ip)
            return True, ip

        # Bloqueo temporal activo
        if st.blocked_until > now:
            secs = int(st.blocked_until - now)
            logger.warning("[GLOBAL-RL] Acceso denegado — IP bloqueada: %s | %ds restantes", ip, secs)
            return True, ip

        # Reset ventana si expiró
        if now - st.window_start > WINDOW_SECONDS:
            st.requests      = 0
            st.window_start  = now

        st.requests += 1

        if st.requests > MAX_REQUESTS:
            st.block_count   += 1
            st.blocked_until  = now + BLOCK_SECONDS

            if st.block_count >= MAX_BLOCKS:
                st.blacklisted = True
                logger.warning(
                    "[GLOBAL-RL] BLACKLIST PERMANENTE — IP: %s | %d bloqueos acumulados",
                    ip, st.block_count,
                )
            else:
                logger.warning(
                    "[GLOBAL-RL] IP BLOQUEADA — %s | bloqueo #%d/%d | hasta %s UTC",
                    ip, st.block_count, MAX_BLOCKS,
                    time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(st.blocked_until)),
                )
            return True, ip

        return False, ip

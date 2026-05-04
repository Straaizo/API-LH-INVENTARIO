"""
token_blacklist.py — Revocación de tokens JWT en memoria.
Los tokens revocados (logout) quedan bloqueados hasta su expiración natural.
"""
import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)

_blacklist: dict[str, float] = {}  # jti -> exp timestamp
_lock = Lock()


def blacklist_token(jti: str, exp: float) -> None:
    with _lock:
        _blacklist[jti] = exp
        _cleanup()
    logger.info("[BLACKLIST] Token revocado: jti=%s", jti[:8])


def is_blacklisted(jti: str) -> bool:
    with _lock:
        return jti in _blacklist


def _cleanup() -> None:
    now = time.time()
    expired = [k for k, v in _blacklist.items() if v < now]
    for k in expired:
        del _blacklist[k]
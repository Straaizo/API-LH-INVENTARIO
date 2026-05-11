"""
global_rate_limit.py — Rate limiting global para todos los endpoints.

Whitelist: RATE_LIMIT_WHITELIST en .env. "*" saltea completamente.
"""
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)

MAX_REQUESTS   = 60
WINDOW_SECONDS = 60
BLOCK_SECONDS  = 1800
MAX_BLOCKS     = 3

_WHITELIST: set[str] = {
    ip.strip()
    for ip in os.getenv("RATE_LIMIT_WHITELIST", "").split(",")
    if ip.strip()
}


@dataclass
class _State:
    requests:      int   = 0
    window_start:  float = field(default_factory=time.time)
    blocked_until: float = 0.0
    block_count:   int   = 0
    blacklisted:   bool  = False


_store: dict[str, _State] = defaultdict(_State)
_lock  = Lock()


def _get_ip(request) -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.client and request.client.host) or "unknown"


def _is_whitelisted(ip: str) -> bool:
    if "*" in _WHITELIST:
        return True
    return ip in _WHITELIST


def check_and_record(request) -> tuple[bool, str]:
    ip  = _get_ip(request)
    if _is_whitelisted(ip):
        return False, ip
    now = time.time()
    with _lock:
        st = _store[ip]
        if st.blacklisted:
            logger.warning("[GLOBAL-RL] BLACKLIST PERMANENTE — IP: %s", ip)
            return True, ip
        if st.blocked_until > now:
            secs = int(st.blocked_until - now)
            logger.warning("[GLOBAL-RL] IP bloqueada: %s | %ds restantes", ip, secs)
            return True, ip
        if now - st.window_start > WINDOW_SECONDS:
            st.requests     = 0
            st.window_start = now
        st.requests += 1
        if st.requests > MAX_REQUESTS:
            st.block_count  += 1
            st.blocked_until = now + BLOCK_SECONDS
            if st.block_count >= MAX_BLOCKS:
                st.blacklisted = True
                logger.warning("[GLOBAL-RL] BLACKLIST PERMANENTE — IP: %s | %d bloqueos", ip, st.block_count)
            else:
                logger.warning("[GLOBAL-RL] IP BLOQUEADA — %s | bloqueo #%d/%d", ip, st.block_count, MAX_BLOCKS)
            return True, ip
        return False, ip

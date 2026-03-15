"""
Simple rate limiting for web chat. Prevents abuse.
Uses in-memory store (no Redis/cache dependency).
"""
import time
from collections import deque
from threading import Lock

# Per-key: deque of timestamps. Clean old entries periodically.
_store: dict[str, deque] = {}
_lock = Lock()
WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 30
MAX_REQUESTS_PER_MINUTE_BURST = 60  # Allow burst for reconnect/retry


def _clean_old(ts_list: deque) -> None:
    """Remove timestamps older than WINDOW_SECONDS."""
    now = time.time()
    while ts_list and ts_list[0] < now - WINDOW_SECONDS:
        ts_list.popleft()


def _get_key(request) -> str:
    """Key for rate limiting: session or IP."""
    session = getattr(request, "session", None)
    if session and session.session_key:
        return f"s:{session.session_key}"
    # Fallback to IP when no session (e.g. first request)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "unknown")
    return f"ip:{ip}"


def is_rate_limited(request) -> bool:
    """
    Check if request should be throttled.
    Returns True if over limit.
    """
    key = _get_key(request)
    now = time.time()
    with _lock:
        if key not in _store:
            _store[key] = deque()
        ts_list = _store[key]
        _clean_old(ts_list)
        if len(ts_list) >= MAX_REQUESTS_PER_WINDOW:
            return True
        ts_list.append(now)
        return False

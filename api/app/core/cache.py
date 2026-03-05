import time
from typing import Any, Callable, Dict, Tuple

# key -> (expires_at, value)
_CACHE: Dict[str, Tuple[float, Any]] = {}


def get_cached(key: str) -> Any | None:
    item = _CACHE.get(key)
    if not item:
        return None
    expires_at, value = item
    if time.time() >= expires_at:
        _CACHE.pop(key, None)
        return None
    return value


def set_cached(key: str, value: Any, ttl_seconds: int) -> Any:
    _CACHE[key] = (time.time() + ttl_seconds, value)
    return value


def cached(key: str, ttl_seconds: int, fn: Callable[[], Any]) -> Any:
    hit = get_cached(key)
    if hit is not None:
        return hit
    return set_cached(key, fn(), ttl_seconds)


def clear_cache(prefix: str | None = None) -> None:
    if prefix is None:
        _CACHE.clear()
        return
    for k in list(_CACHE.keys()):
        if k.startswith(prefix):
            _CACHE.pop(k, None)
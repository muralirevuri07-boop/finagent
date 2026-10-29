"""
av_cache.py
Simple TTL cache for Alpha Vantage API responses.

Free tier = 25 req/day. This cache stores results in memory (process lifetime)
AND on disk (/tmp/av_cache.json) so restarts don't wipe everything.

TTL: 6 hours — data stays fresh enough for intraday use.
"""
import json
import os
import time
from typing import Any

_CACHE_FILE = "/tmp/av_cache.json"
_TTL_SECONDS = 6 * 3600   # 6 hours

# In-memory store: { "symbol|endpoint": {"ts": float, "data": Any} }
_mem: dict = {}


def _load_disk() -> None:
    """Load persisted cache from disk into memory on first use."""
    global _mem
    if _mem:
        return
    try:
        with open(_CACHE_FILE, "r") as f:
            _mem = json.load(f)
    except Exception:
        _mem = {}


def _save_disk() -> None:
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump(_mem, f)
    except Exception:
        pass


def cache_key(symbol: str, endpoint: str) -> str:
    return f"{symbol.upper()}|{endpoint}"


def get(symbol: str, endpoint: str) -> Any | None:
    """Return cached value if still fresh, else None."""
    _load_disk()
    k = cache_key(symbol, endpoint)
    entry = _mem.get(k)
    if not entry:
        return None
    if time.time() - entry["ts"] > _TTL_SECONDS:
        del _mem[k]
        return None
    return entry["data"]


def set(symbol: str, endpoint: str, data: Any) -> None:
    """Store data in cache."""
    _load_disk()
    k = cache_key(symbol, endpoint)
    _mem[k] = {"ts": time.time(), "data": data}
    _save_disk()


def stats() -> dict:
    """Return cache stats for debugging."""
    _load_disk()
    now = time.time()
    fresh = sum(1 for v in _mem.values() if now - v["ts"] <= _TTL_SECONDS)
    return {"total_entries": len(_mem), "fresh": fresh, "ttl_hours": _TTL_SECONDS // 3600}

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cachetools import TTLCache

from api_core.config import settings

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency in local dev
    redis = None


@dataclass(frozen=True)
class CacheStats:
    size: int
    maxsize: int
    ttl_seconds: int
    backend: str


class CacheNamespace:
    def __init__(self, name: str, maxsize: int, ttl_seconds: int, redis_client: Any = None):
        self.name = name
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._redis = redis_client
        self._memory = TTLCache(maxsize=maxsize, ttl=ttl_seconds)
        self._lock = threading.RLock()

    def _redis_key(self, key: str) -> str:
        return f"borsapy:{self.name}:{key}"

    def _get_redis(self, key: str) -> Any | None:
        if not self._redis:
            return None
        raw = self._redis.get(self._redis_key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def _set_redis(self, key: str, value: Any) -> None:
        if not self._redis:
            return
        try:
            self._redis.setex(self._redis_key(key), self.ttl_seconds, json.dumps(value, default=str))
        except Exception:
            return

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key in self._memory:
                return self._memory[key]
        value = self._get_redis(key)
        if value is not None:
            with self._lock:
                self._memory[key] = value
        return value

    def set(self, key: str, value: Any) -> Any:
        with self._lock:
            self._memory[key] = value
        self._set_redis(key, value)
        return value

    def get_or_set(self, key: str, func: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        with self._lock:
            if key in self._memory:
                return self._memory[key]
            value = func()
            self._memory[key] = value
        self._set_redis(key, value)
        return value

    def stats(self) -> CacheStats:
        with self._lock:
            size = len(self._memory)
        return CacheStats(
            size=size,
            maxsize=self.maxsize,
            ttl_seconds=self.ttl_seconds,
            backend="redis+memory" if self._redis else "memory",
        )


def _build_redis_client():
    if not settings.redis_url or redis is None:
        return None
    try:
        return redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)
    except Exception:
        return None


_redis_client = _build_redis_client()

REALTIME_CACHE = CacheNamespace("realtime", settings.realtime_cache.maxsize, settings.realtime_cache.ttl_seconds, _redis_client)
MARKET_CACHE = CacheNamespace("market", settings.market_cache.maxsize, settings.market_cache.ttl_seconds, _redis_client)
STATIC_CACHE = CacheNamespace("static", settings.static_cache.maxsize, settings.static_cache.ttl_seconds, _redis_client)


def get_cached_realtime(key: str, func: Callable[[], Any]) -> Any:
    return REALTIME_CACHE.get_or_set(key, func)


def get_cached_market(key: str, func: Callable[[], Any]) -> Any:
    return MARKET_CACHE.get_or_set(key, func)


def get_cached_static(key: str, func: Callable[[], Any]) -> Any:
    return STATIC_CACHE.get_or_set(key, func)


def cache_overview() -> dict[str, dict[str, Any]]:
    return {
        "realtime": REALTIME_CACHE.stats().__dict__,
        "market": MARKET_CACHE.stats().__dict__,
        "static": STATIC_CACHE.stats().__dict__,
    }

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cachetools import TTLCache

from api_core.config import settings

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency in local dev
    redis = None

logger = logging.getLogger("finansapi.cache")


@dataclass(frozen=True)
class CacheStats:
    size: int
    maxsize: int
    ttl_seconds: int
    backend: str


class SingleFlight:
    """Request coalescing: ensures only one worker thread fetches an in-flight key."""

    def __init__(self):
        self._lock = threading.Lock()
        self._calls: dict[str, tuple[threading.Event, list[Any]]] = {}

    def execute(self, key: str, func: Callable[[], Any]) -> Any:
        with self._lock:
            if key in self._calls:
                event, result_holder = self._calls[key]
                first_caller = False
            else:
                event = threading.Event()
                result_holder = [None, None]  # [result, exception]
                self._calls[key] = (event, result_holder)
                first_caller = True

        if not first_caller:
            event.wait(timeout=30.0)
            if result_holder[1] is not None:
                raise result_holder[1]
            return result_holder[0]

        try:
            val = func()
            result_holder[0] = val
            return val
        except Exception as exc:
            result_holder[1] = exc
            raise
        finally:
            with self._lock:
                event.set()
                self._calls.pop(key, None)


_single_flight = SingleFlight()


class CacheNamespace:
    def __init__(self, name: str, maxsize: int, ttl_seconds: int, redis_client: Any = None):
        self.name = name
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._redis = redis_client
        # Memory cache holds items for up to 5x standard TTL to support stale serving
        self._memory = TTLCache(maxsize=maxsize, ttl=max(ttl_seconds * 5, 300))
        self._lock = threading.RLock()
        self._refreshing_keys: set[str] = set()

    def _redis_key(self, key: str) -> str:
        return f"finansapi:{self.name}:{key}"

    def _get_redis(self, key: str) -> Any | None:
        if not self._redis:
            return None
        try:
            raw = self._redis.get(self._redis_key(key))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def _set_redis(self, key: str, value: Any, ttl: int | None = None) -> None:
        if not self._redis:
            return
        try:
            effective_ttl = ttl or max(self.ttl_seconds * 5, 300)
            self._redis.setex(self._redis_key(key), effective_ttl, json.dumps(value, default=str))
        except Exception:
            return

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key in self._memory:
                entry = self._memory[key]
                if isinstance(entry, dict) and "__swr_data__" in entry:
                    return entry["__swr_data__"]
                return entry
        redis_val = self._get_redis(key)
        if redis_val is not None:
            with self._lock:
                self._memory[key] = redis_val
            if isinstance(redis_val, dict) and "__swr_data__" in redis_val:
                return redis_val["__swr_data__"]
            return redis_val
        return None

    def set(self, key: str, value: Any) -> Any:
        with self._lock:
            self._memory[key] = value
        self._set_redis(key, value)
        return value

    def get_or_set(self, key: str, func: Callable[[], Any], stale_ttl: int | None = None) -> Any:
        """
        Stale-While-Revalidate + Single-Flight engine.
        - If cached and fresh: returns immediately (< 1ms).
        - If cached but stale: returns immediately, refreshes in background.
        - If not in cache: fetches synchronously using SingleFlight (prevents duplicate requests).
        """
        stale_limit = stale_ttl or self.ttl_seconds
        now = time.time()

        with self._lock:
            entry = self._memory.get(key)

        if entry is None:
            redis_entry = self._get_redis(key)
            if redis_entry is not None:
                with self._lock:
                    self._memory[key] = redis_entry
                entry = redis_entry

        if entry is not None:
            if isinstance(entry, dict) and "__swr_data__" in entry:
                data = entry["__swr_data__"]
                stale_at = entry.get("__stale_at__", 0)

                # Fresh! Return immediately
                if now < stale_at:
                    return data

                # Stale! Return immediately, trigger background refresh
                self._trigger_background_refresh(key, func, stale_limit)
                return data
            else:
                return entry

        # Cache miss: fetch via Single-Flight
        return self._fetch_and_cache(key, func, stale_limit)

    def _fetch_and_cache(self, key: str, func: Callable[[], Any], stale_limit: int) -> Any:
        def fetch_wrapper():
            val = func()
            if isinstance(val, dict) and val.get("error"):
                return val

            now = time.time()
            swr_wrapper = {
                "__swr_data__": val,
                "__stale_at__": now + stale_limit,
                "__created_at__": now,
            }
            with self._lock:
                self._memory[key] = swr_wrapper
            self._set_redis(key, swr_wrapper)
            return val

        try:
            return _single_flight.execute(key, fetch_wrapper)
        except Exception:
            # If fetch fails, try to return stale data if available
            with self._lock:
                fallback = self._memory.get(key)
            if fallback and isinstance(fallback, dict) and "__swr_data__" in fallback:
                return fallback["__swr_data__"]
            raise

    def _trigger_background_refresh(self, key: str, func: Callable[[], Any], stale_limit: int) -> None:
        with self._lock:
            if key in self._refreshing_keys:
                return
            self._refreshing_keys.add(key)

        def bg_task():
            try:
                val = func()
                if not (isinstance(val, dict) and val.get("error")):
                    now = time.time()
                    swr_wrapper = {
                        "__swr_data__": val,
                        "__stale_at__": now + stale_limit,
                        "__created_at__": now,
                    }
                    with self._lock:
                        self._memory[key] = swr_wrapper
                    self._set_redis(key, swr_wrapper)
            except Exception as exc:
                logger.debug("Background SWR refresh failed for %s: %s", key, exc)
            finally:
                with self._lock:
                    self._refreshing_keys.discard(key)

        thread = threading.Thread(target=bg_task, daemon=True, name=f"swr-refresh-{key[:20]}")
        thread.start()

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
    return REALTIME_CACHE.get_or_set(key, func, stale_ttl=settings.realtime_cache.ttl_seconds)


def get_cached_market(key: str, func: Callable[[], Any]) -> Any:
    return MARKET_CACHE.get_or_set(key, func, stale_ttl=settings.market_cache.ttl_seconds)


def get_cached_static(key: str, func: Callable[[], Any]) -> Any:
    return STATIC_CACHE.get_or_set(key, func, stale_ttl=settings.static_cache.ttl_seconds)


def cache_overview() -> dict[str, dict[str, Any]]:
    return {
        "realtime": REALTIME_CACHE.stats().__dict__,
        "market": MARKET_CACHE.stats().__dict__,
        "static": STATIC_CACHE.stats().__dict__,
    }

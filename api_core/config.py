import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CacheNamespaceConfig:
    maxsize: int
    ttl_seconds: int


@dataclass(frozen=True)
class Settings:
    api_key: str = os.getenv("API_KEY", "CHANGE_ME")
    render_external_url: str | None = os.getenv("RENDER_EXTERNAL_URL")
    redis_url: str | None = os.getenv("REDIS_URL")
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
    gzip_minimum_size: int = int(os.getenv("GZIP_MINIMUM_SIZE", "1024"))
    cors_allow_origins: tuple[str, ...] = tuple(filter(None, os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")))
    realtime_cache: CacheNamespaceConfig = CacheNamespaceConfig(maxsize=500, ttl_seconds=30)
    market_cache: CacheNamespaceConfig = CacheNamespaceConfig(maxsize=200, ttl_seconds=60)
    static_cache: CacheNamespaceConfig = CacheNamespaceConfig(maxsize=1000, ttl_seconds=86400)


settings = Settings()

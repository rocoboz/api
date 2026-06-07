from __future__ import annotations

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter

from api_core.config import settings


api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


def get_client_ip(request: Request) -> str:
    for header in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
        raw = request.headers.get(header)
        if raw:
            return raw.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


_limiter_kwargs = {
    "key_func": get_client_ip,
    "default_limits": [f"{settings.rate_limit_default_per_minute}/minute"],
    "application_limits": [f"{settings.rate_limit_application_per_minute}/minute"],
    "headers_enabled": True,
}

if settings.redis_url:
    _limiter_kwargs["storage_uri"] = settings.redis_url

limiter = Limiter(**_limiter_kwargs)


async def verify_api_key(api_key: str = Security(api_key_header)) -> bool:
    if settings.api_key == "OPEN":
        return True
    if api_key and api_key == settings.api_key:
        return True
    raise HTTPException(status_code=403, detail="Invalid or Missing API Key")

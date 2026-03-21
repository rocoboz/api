from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from api_core.config import settings


api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)
limiter = Limiter(key_func=get_remote_address)


async def verify_api_key(api_key: str = Security(api_key_header)) -> bool:
    if settings.api_key == "OPEN":
        return True
    if api_key and api_key == settings.api_key:
        return True
    raise HTTPException(status_code=403, detail="Invalid or Missing API Key")

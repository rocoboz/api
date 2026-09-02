from fastapi import APIRouter, Depends

from api_core.services.cache import cache_overview
from api_core.services.response import api_ok
from api_core.services.security import verify_api_key

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/cache", dependencies=[Depends(verify_api_key)])
def cache_stats():
    return api_ok(cache_overview())


@router.api_route("/health", methods=["GET", "HEAD"])
def health():
    return api_ok({"status": "healthy"})


@router.api_route("/ready", methods=["GET", "HEAD"])
def ready():
    return api_ok({"status": "ready"})

from fastapi import APIRouter

from api_core.services.cache import cache_overview
from api_core.services.response import api_ok

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/cache")
def cache_stats():
    return api_ok(cache_overview())


@router.get("/health")
def health():
    return api_ok({"status": "healthy"})


@router.get("/ready")
def ready():
    return api_ok({"status": "ready"})

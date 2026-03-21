from fastapi import APIRouter

from api_core.services.response import api_ok

router = APIRouter()


@router.get("/ping")
def ping():
    return api_ok({"status": "ok"})


@router.get("/")
def home():
    return api_ok(
        {
            "service": "BorsaPy Ultimate API",
            "version": "2.0.0",
            "github": "https://github.com/rocoboz/api",
            "docs": "/docs",
        }
    )

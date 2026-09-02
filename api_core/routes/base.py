from fastapi import APIRouter

from api_core.services.response import api_ok

router = APIRouter()


@router.api_route("/ping", methods=["GET", "HEAD"])
def ping():
    return api_ok({"status": "ok"})


@router.api_route("/", methods=["GET", "HEAD"])
def home():
    return api_ok(
        {
            "service": "FinansAPI",
            "version": "3.0.0",
            "github": "https://github.com/rocoboz/api",
            "docs": "/docs",
        }
    )

from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from api_core.config import settings
from api_core.routes.base import router as base_router
from api_core.routes.economy import router as economy_router
from api_core.routes.funds import router as funds_router
from api_core.routes.market import router as market_router
from api_core.routes.ops import router as ops_router
from api_core.routes.search import router as search_router
from api_core.routes.stocks import router as stocks_router
from api_core.services.observability import request_timing_middleware
from api_core.services.security import limiter


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    app = FastAPI(
        title="BorsaPy Ultimate API",
        description="Professional Financial Gateway for Turkish Markets.",
        version="2.0.0",
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_minimum_size)
    app.middleware("http")(request_timing_middleware)

    app.include_router(base_router)
    app.include_router(ops_router)
    app.include_router(stocks_router)
    app.include_router(funds_router)
    app.include_router(market_router)
    app.include_router(economy_router)
    app.include_router(search_router)

    @app.on_event("startup")
    async def startup_event():
        async def ping_regularly():
            if not settings.render_external_url:
                return
            while True:
                await asyncio.sleep(14 * 60)
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        await client.get(f"{settings.render_external_url}/ping")
                except Exception:
                    pass

        asyncio.create_task(ping_regularly())

    return app

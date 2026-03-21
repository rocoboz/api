from __future__ import annotations

import json
import logging
import time
from typing import Callable

from fastapi import Request, Response

logger = logging.getLogger("borsapy.api")


async def request_timing_middleware(request: Request, call_next: Callable):
    started = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    logger.info(
        json.dumps(
            {
                "event": "request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
            ensure_ascii=False,
        )
    )
    return response

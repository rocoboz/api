from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


def now_iso() -> str:
    return datetime.now(ZoneInfo("Europe/Istanbul")).isoformat()


def api_ok(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "error": None,
        "meta": meta or {},
    }


def pagination_meta(limit: int, offset: int, count: int, **extra: Any) -> dict[str, Any]:
    meta = {
        "limit": limit,
        "offset": offset,
        "count": count,
        "generated_at": now_iso(),
    }
    meta.update(extra)
    return meta

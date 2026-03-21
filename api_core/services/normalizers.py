from __future__ import annotations

import json
from typing import Any

import numpy as np

from api_core.services.response import now_iso


def clean_json_val(val: Any) -> Any:
    """Safely handle NaN/Inf while preserving valid zeros."""
    if val is None:
        return None
    try:
        if np.isnan(val) or np.isinf(val):
            return None
    except Exception:
        pass
    return val


def df_to_json(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        return [{k: clean_json_val(v) for k, v in item.items()} if isinstance(item, dict) else item for item in data]
    if hasattr(data, "empty") and data.empty:
        return []
    return json.loads(data.to_json(orient="records", date_format="iso"))


def normalize_stock_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": row.get("symbol") or row.get("ticker") or row.get("code") or row.get("name"),
        "name": row.get("long_name") or row.get("short_name") or row.get("name") or row.get("symbol") or row.get("ticker"),
        "price": clean_json_val(row.get("price")),
        "change": clean_json_val(row.get("change")),
        "changePercent": clean_json_val(row.get("change")),
        "volume": clean_json_val(row.get("volume")),
        "market_cap": clean_json_val(row.get("market_cap")),
        "pe": clean_json_val(row.get("pe")),
        "pddd": clean_json_val(row.get("pddd")),
        "last_update": now_iso(),
    }


def normalize_fund_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "fund_code": row.get("fund_code") or row.get("code"),
        "name": row.get("name"),
        "fund_type": row.get("fund_type") or row.get("category") or "Genel",
        "price": clean_json_val(row.get("price")),
        "change": clean_json_val(row.get("change")),
        "risk_value": clean_json_val(row.get("risk_value")),
        "daily_return": clean_json_val(row.get("daily_return")),
        "fund_size": clean_json_val(row.get("fund_size")),
        "investor_count": clean_json_val(row.get("investor_count")),
        "return_1m": clean_json_val(row.get("return_1m")),
        "return_3m": clean_json_val(row.get("return_3m")),
        "return_6m": clean_json_val(row.get("return_6m")),
        "return_ytd": clean_json_val(row.get("return_ytd")),
        "return_1y": clean_json_val(row.get("return_1y")),
    }

from __future__ import annotations

import json
import unicodedata
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


def infer_fund_risk(*texts: Any) -> int | None:
    translation_table = str.maketrans({
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ü": "u",
        "Ü": "u",
        "ö": "o",
        "Ö": "o",
        "ç": "c",
        "Ç": "c",
    })
    normalized = unicodedata.normalize(
        "NFKD",
        " ".join(str(text or "").strip().lower() for text in texts if text).translate(translation_table),
    ).encode("ascii", "ignore").decode("ascii")
    if not normalized:
        return None

    rules: list[tuple[list[str], int]] = [
        (["para piyasasi", "likit", "kisa vadeli"], 1),
        (["borclanma", "tahvil", "bono", "repo", "mevduat", "kira sertifikasi", "katilim"], 2),
        (["eurobond", "dis borclanma", "sermaye piyasasi araci"], 3),
        (["degisken", "karma", "dengeli", "fon sepeti"], 4),
        (["altin", "gumus", "kiymetli maden", "emtia", "doviz"], 5),
        (["hisse senedi", "hisse yogun", "temettu", "endeks"], 6),
        (["serbest", "girisim", "gayrimenkul", "yabanci"], 7),
    ]

    for keywords, risk in rules:
        if any(keyword in normalized for keyword in keywords):
            return risk

    return None


def resolve_fund_risk(reported_risk: Any, *texts: Any) -> tuple[int | None, str | None]:
    cleaned_reported = clean_json_val(reported_risk)
    if isinstance(cleaned_reported, (int, float)):
        risk_value = int(cleaned_reported)
        if 1 <= risk_value <= 7:
            return risk_value, "reported"

    inferred = infer_fund_risk(*texts)
    if inferred is not None:
        return inferred, "inferred"

    return None, None


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
    risk_value, risk_source = resolve_fund_risk(
        row.get("risk_value"),
        row.get("fund_type"),
        row.get("category"),
        row.get("name"),
    )
    return {
        "fund_code": row.get("fund_code") or row.get("code"),
        "name": row.get("name"),
        "fund_type": row.get("fund_type") or row.get("category") or "Genel",
        "price": clean_json_val(row.get("price")),
        "change": clean_json_val(row.get("change")),
        "risk_value": risk_value,
        "risk_source": risk_source,
        "daily_return": clean_json_val(row.get("daily_return")),
        "fund_size": clean_json_val(row.get("fund_size")),
        "investor_count": clean_json_val(row.get("investor_count")),
        "return_1m": clean_json_val(row.get("return_1m")),
        "return_3m": clean_json_val(row.get("return_3m")),
        "return_6m": clean_json_val(row.get("return_6m")),
        "return_ytd": clean_json_val(row.get("return_ytd")),
        "return_1y": clean_json_val(row.get("return_1y")),
    }

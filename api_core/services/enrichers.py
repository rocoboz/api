from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from api_core.services.normalizers import clean_json_val, compact_payload, normalize_stock_row
from api_core.services.providers import Ticker


def quote_payload_for_symbol(symbol: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    ticker = Ticker(symbol)

    try:
        payload.update(dict(ticker.fast_info))
    except Exception:
        pass

    try:
        info = ticker.info
        payload.update(
            {
                "price": clean_json_val(info.get("last")),
                "last_price": clean_json_val(info.get("last_price") or info.get("last") or info.get("currentPrice")),
                "change": clean_json_val(info.get("change") or info.get("regularMarketChange")),
                "change_percent": clean_json_val(info.get("change_percent") or info.get("regularMarketChangePercent")),
                "volume": clean_json_val(info.get("volume") or info.get("regularMarketVolume")),
                "market_cap": clean_json_val(info.get("market_cap") or info.get("marketCap")),
                "pe": clean_json_val(info.get("pe") or info.get("pe_ratio") or info.get("trailingPE")),
                "pddd": clean_json_val(info.get("pddd") or info.get("pb_ratio") or info.get("priceToBook")),
            }
        )
    except Exception:
        pass

    return payload


def enrich_stock_row(row: dict[str, Any]) -> dict[str, Any]:
    symbol = row.get("symbol") or row.get("ticker") or row.get("code")
    if not symbol:
        return compact_payload(normalize_stock_row(row))

    try:
        base = dict(row)
        merged = {**base, **quote_payload_for_symbol(str(symbol))}
        normalized = normalize_stock_row(merged)
        normalized["name"] = base.get("name") or normalized.get("name")
        return compact_payload(normalized)
    except Exception:
        return compact_payload(normalize_stock_row(row))


def enrich_stock_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows

    max_workers = min(8, max(1, len(rows)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(enrich_stock_row, rows))

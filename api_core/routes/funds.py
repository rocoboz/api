from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Query, Request, Response

from api_core.services.cache import get_cached_market, get_cached_realtime, get_cached_static
from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json, normalize_fund_row, resolve_fund_risk
from api_core.services.providers import Fund, Index, parse_fund_holdings_no_llm, screen_funds
from api_core.services.response import api_ok, pagination_meta
from api_core.services.security import limiter

router = APIRouter(prefix="/funds", tags=["funds"])


def _enrich_rows_with_details(rows: list[dict]):
    if not rows:
        return rows

    def enrich(row: dict):
        code = row.get("fund_code")
        if not code:
            return row
        try:
            info = Fund(code).info or {}
            enriched = dict(row)

            risk_value, risk_source = resolve_fund_risk(
                info.get("risk_value"),
                info.get("category"),
                info.get("fund_type"),
                info.get("name"),
            )

            # /funds/list source only includes period returns; fill realtime/detail fields
            # from the per-fund detail payload so callers don't get avoidable nulls.
            for field in ("price", "daily_return", "fund_size", "investor_count"):
                if enriched.get(field) is None:
                    enriched[field] = clean_json_val(info.get(field))

            if enriched.get("change") is None:
                enriched["change"] = clean_json_val(info.get("daily_return"))

            if risk_value is not None:
                enriched["risk_value"] = risk_value
                enriched["risk_source"] = risk_source
        except Exception:
            return row
        return enriched

    max_workers = min(8, max(1, len(rows)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(enrich, rows))


@router.get("/list")
def list_funds(response: Response, fund_type: str = "YAT", limit: int = 50, offset: int = 0, envelope: bool = False):
    def fetch():
        fetch_limit = max(offset + limit, 2000)
        df = screen_funds(fund_type=fund_type, limit=fetch_limit)
        if df.empty:
            return []
        sliced = df.iloc[offset : offset + limit]
        rows = [normalize_fund_row(row) for row in df_to_json(sliced)]
        return _enrich_rows_with_details(rows)

    rows = get_cached_static(f"FUND_LIST_V3_{fund_type}_{limit}_{offset}", fetch)
    meta = pagination_meta(limit=limit, offset=offset, count=len(rows), fund_type=fund_type)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)
    response.headers["X-Count"] = str(len(rows))
    return api_ok(rows, meta) if envelope else rows


@router.get("/screener")
def tefas_screener(response: Response, fund_type: str = "YAT", envelope: bool = False):
    def fetch():
        return [compact_payload(row) for row in df_to_json(screen_funds(fund_type=fund_type, limit=2000))]

    rows = get_cached_market(f"FUND_SCREENER_{fund_type}", fetch)
    meta = {"fund_type": fund_type, "count": len(rows)}
    return api_ok(rows, meta) if envelope else rows


@router.get("/{code}")
def get_fund_detail(code: str):
    code = code.upper()

    def fetch():
        try:
            f = Fund(code)
            info = f.info
            if not info:
                return {"error": "Fund not found"}
            cleaned = {k: clean_json_val(v) for k, v in info.items()}
            risk_value, risk_source = resolve_fund_risk(
                cleaned.get("risk_value"),
                cleaned.get("category"),
                cleaned.get("fund_type"),
                cleaned.get("name"),
            )
            cleaned["risk_value"] = risk_value
            cleaned["risk_source"] = risk_source
            return compact_payload(cleaned)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_static(f"FUND_DETAIL_{code}", fetch)


@router.get("/{code}/history")
def get_fund_history(code: str, period: str = "1mo"):
    code = code.upper()

    def fetch():
        try:
            f = Fund(code)
            df = f.history(period=period)
            if df.empty:
                return []
            return df_to_json(df)
        except Exception:
            return []

    return get_cached_realtime(f"FUND_HISTORY_{code}_{period}", fetch)


@router.get("/{code}/estimated-return")
@limiter.limit("10/minute")
def get_fund_estimated_return(request: Request, code: str):
    code = code.upper()

    def fetch():
        f = Fund(code)
        info = f.info
        holdings = get_cached_static(f"HOLDINGS_SCAN_{code}", lambda: parse_fund_holdings_no_llm(code))
        try:
            bist = Index("XU100").info.get("change_percent", 0) / 100
        except Exception:
            bist = 0
        daily_fixed = 0.0012
        estimate = 0.0
        details = []
        mode = ""
        alloc = info.get("allocation", [])
        tefas_hisse_weight = sum((a.get("weight", 0) / 100) for a in alloc if any(x in a.get("asset_name", "").lower() for x in ["hisse senedi", "stock", "equity"]))
        if holdings:
            stocks_total_weight = 0
            stocks_calculated_return = 0
            changes = {}
            try:
                from tradingview_screener import Query

                _, df = Query().set_markets("turkey").select("name", "change").get_scanner_data()
                if not df.empty:
                    changes = dict(zip(df["name"], df["change"].astype(float)))
            except Exception:
                pass
            for h in holdings:
                sym = h["symbol"]
                weight = h["weight"] / 100
                s_ret = changes.get(sym, bist * 100) / 100
                stocks_total_weight += weight
                stocks_calculated_return += weight * s_ret
                details.append({"asset": sym, "weight": round(weight * 100, 2), "daily_return": round(s_ret * 100, 2), "impact": round(weight * s_ret * 100, 4)})
            if tefas_hisse_weight > stocks_total_weight:
                diff = tefas_hisse_weight - stocks_total_weight
                stocks_calculated_return += diff * bist
                details.append({"asset": "BIST100 Proxy", "weight": round(diff * 100, 2), "daily_return": round(bist * 100, 2), "impact": round(diff * bist * 100, 4)})
            estimate += stocks_calculated_return
            mode = "Deep Scan (Specific Holdings)"
        else:
            hisse_weight = tefas_hisse_weight
            estimate += hisse_weight * bist
            details.append({"asset": "BIST100 Proxy", "weight": round(hisse_weight * 100, 2), "daily_return": round(bist * 100, 2), "impact": round(hisse_weight * bist * 100, 4)})
            mode = "TEFAS Allocation Proxy"
        for item in alloc:
            name = item.get("asset_name", "").lower()
            weight = item.get("weight", 0) / 100
            if any(x in name for x in ["hisse senedi", "stock", "equity"]):
                continue
            if any(x in name for x in ["repo", "mevduat", "bono", "tahvil", "cash", "likit", "ters repo"]):
                estimate += weight * daily_fixed
                details.append({"asset": item.get("asset_name"), "weight": round(weight * 100, 2), "daily_return": round(daily_fixed * 100, 2), "impact": round(weight * daily_fixed * 100, 4)})
        return {
            "fund_code": code,
            "estimated_daily_return": round(estimate * 100, 3),
            "calculation_mode": mode,
            "last_allocation_date": info.get("date"),
            "breakdown": details,
            "benchmarks": {"bist100": round(bist * 100, 2), "usdtry": 0, "gold": 0},
        }

    return get_cached_realtime(f"FUND_EST_{code}", fetch)

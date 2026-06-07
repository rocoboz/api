from __future__ import annotations

import json

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query, Request, Response

from api_core.services.cache import get_cached_market, get_cached_realtime, get_cached_static
from api_core.services.enrichers import enrich_stock_row, enrich_stock_rows
from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json
from api_core.services.providers import Ticker, Fund, get_kap_provider, market
from api_core.services.response import api_ok, pagination_meta
from api_core.services.security import limiter

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/list")
@limiter.limit("30/minute")
def list_stocks(request: Request, response: Response, limit: int = 50, offset: int = 0, envelope: bool = False):
    def fetch():
        try:
            df = market.companies()
            if df.empty:
                return []
            sliced = df.iloc[offset : offset + limit]
            return enrich_stock_rows(df_to_json(sliced))
        except Exception:
            return []

    rows = get_cached_static(f"ST_LIST_V2_{limit}_{offset}", fetch)
    meta = pagination_meta(limit=limit, offset=offset, count=len(rows))
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)
    response.headers["X-Count"] = str(len(rows))
    return api_ok(rows, meta) if envelope else rows


@router.get("/compare")
@limiter.limit("20/minute")
def compare(request: Request, response: Response, symbols: str = Query(...), envelope: bool = False):
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    def fetch():
        return [enrich_stock_row({"symbol": symbol, "name": symbol}) for symbol in sym_list]

    rows = get_cached_market(f"COMPARE_{symbols}", fetch)
    meta = {"count": len(rows), "symbols": sym_list}
    return api_ok(rows, meta) if envelope else rows


@router.get("/{symbol}")
@limiter.limit("30/minute")
def get_stock(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        tk = Ticker(symbol)
        try:
            info = dict(tk.fast_info) if hasattr(tk, "fast_info") else dict(tk.info)
        except Exception:
            info = dict(tk.info)

        def fetch_kap():
            try:
                kap = get_kap_provider()
                return kap.get_company_details(symbol)
            except Exception:
                return {}

        info["details"] = get_cached_static(f"KAP_DETAILS_{symbol}", fetch_kap)
        return compact_payload({"symbol": symbol, "data": info})

    return get_cached_market(f"STOCK_{symbol}", fetch)


@router.get("/{symbol}/history")
@limiter.limit("30/minute")
def get_history(request: Request, response: Response, symbol: str, period: str = "1mo", interval: str = "1d"):
    symbol = symbol.upper()

    def fetch():
        if len(symbol) == 3:
            obj = Fund(symbol)
            df = obj.history(period=period)
        else:
            obj = Ticker(symbol)
            df = obj.history(period=period, interval=interval)
        if df.empty:
            return {"error": "No data"}
        return df_to_json(df)

    return get_cached_realtime(f"HIST_{symbol}_{period}_{interval}", fetch)


@router.get("/{symbol}/depth")
@limiter.limit("10/minute")
def get_simulated_depth(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        tk = Ticker(symbol)
        hist = tk.history(period="1d", interval="5m")
        if hist.empty:
            return {"error": "Insufficient intraday data"}

        low, high = hist["Low"].min(), hist["High"].max()
        if high == low:
            high += 0.01

        bins = np.linspace(low, high, 20)
        hist["PriceBin"] = pd.cut(hist["Close"], bins=bins, labels=bins[:-1])
        vp = hist.groupby("PriceBin", observed=False)["Volume"].sum().reset_index()
        vp = vp.dropna().sort_values("PriceBin", ascending=False)
        total_vol = vp["Volume"].sum()
        result = []
        for _, row in vp.iterrows():
            result.append(
                {
                    "price": round(float(row["PriceBin"]), 2),
                    "volume": int(row["Volume"]),
                    "weight": round((row["Volume"] / total_vol) * 100, 1),
                }
            )
        return {"symbol": symbol, "simulated_depth": result, "method": "Volume-at-Price Profile"}

    return get_cached_realtime(f"DEPTH_{symbol}", fetch)


@router.get("/{symbol}/disclosures")
@limiter.limit("15/minute")
def get_disclosures(request: Request, response: Response, symbol: str, limit: int = 15):
    def fetch():
        kap = get_kap_provider()
        return df_to_json(kap.get_disclosures(symbol, limit))

    return get_cached_market(f"DISC_{symbol}_{limit}", fetch)


@router.get("/{symbol}/dividends")
@limiter.limit("20/minute")
def get_dividends(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        try:
            tk = Ticker(symbol)
            divs = tk.dividends
            if divs is None or divs.empty:
                return []
            df = divs.reset_index()
            df = df.rename(columns={"Date": "date", "Amount": "amount", "GrossRate": "gross", "NetRate": "net"})
            return df_to_json(df)
        except Exception:
            return []

    return get_cached_static(f"DIVS_{symbol}", fetch)


@router.get("/{symbol}/financials")
@limiter.limit("20/minute")
def get_financials(request: Request, response: Response, symbol: str, type: str = "income"):
    symbol = symbol.upper()

    def fetch():
        try:
            tk = Ticker(symbol)
            if type == "balance":
                df = tk.balance_sheet
            elif type == "cash":
                df = tk.cash_flow
            else:
                df = tk.income_stmt
            if df is None or df.empty:
                return {"error": "No data"}
            return compact_payload(json.loads(df.to_json(date_format="iso")))
        except Exception:
            return {"error": "Financial data currently unavailable"}

    return get_cached_static(f"FIN_{symbol}_{type}", fetch)

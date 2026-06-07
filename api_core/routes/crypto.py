from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from api_core.services.cache import get_cached_market, get_cached_realtime, get_cached_static
from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json
from api_core.services.providers import Crypto, crypto_pairs
from api_core.services.response import api_ok, pagination_meta
from api_core.services.security import limiter

router = APIRouter(prefix="/crypto", tags=["crypto"])


@router.get("/list")
@limiter.limit("20/minute")
def list_crypto_pairs(request: Request, response: Response, quote: str = "TRY", envelope: bool = False):
    def fetch():
        try:
            return crypto_pairs(quote=quote)
        except Exception:
            return []

    pairs = get_cached_static(f"CRYPTO_PAIRS_{quote.upper()}", fetch)
    meta = {"quote": quote, "count": len(pairs)}
    return api_ok(pairs, meta) if envelope else pairs


@router.get("/{pair}")
@limiter.limit("30/minute")
def get_crypto_detail(request: Request, response: Response, pair: str):
    pair = pair.upper()

    def fetch():
        try:
            c = Crypto(pair)
            info = c.current
            if not info:
                return {"error": f"Crypto pair {pair} not found or unavailable"}
            return compact_payload({k: clean_json_val(v) for k, v in info.items()})
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_realtime(f"CRYPTO_{pair}", fetch)


@router.get("/{pair}/history")
@limiter.limit("30/minute")
def get_crypto_history(request: Request, response: Response, pair: str, period: str = "1mo", interval: str = "1d"):
    pair = pair.upper()

    def fetch():
        try:
            c = Crypto(pair)
            df = c.history(period=period, interval=interval)
            if df.empty:
                return {"error": "No historical data available"}
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_realtime(f"CRYPTO_HIST_{pair}_{period}_{interval}", fetch)

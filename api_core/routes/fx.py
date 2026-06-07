from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from api_core.services.cache import get_cached_market, get_cached_realtime, get_cached_static
from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json
from api_core.services.providers import FX, banks, metal_institutions
from api_core.services.response import api_ok
from api_core.services.security import limiter

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("/list")
@limiter.limit("20/minute")
def list_fx_info(request: Request, response: Response, envelope: bool = False):
    def fetch():
        try:
            return {
                "banks": banks(),
                "metal_institutions": metal_institutions(),
                "supported_assets_hint": [
                    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", 
                    "gram-altin", "ons-altin", "gram-gumus", "gram-platin", 
                    "ceyrek-altin", "yarim-altin", "tam-altin", 
                    "cumhuriyet-altin", "ata-altin", "BRENT", "XAG-USD"
                ]
            }
        except Exception:
            return {"banks": [], "metal_institutions": []}

    data = get_cached_static("FX_INFO_LIST", fetch)
    return api_ok(data) if envelope else data


@router.get("/{asset}")
@limiter.limit("30/minute")
def get_fx_detail(request: Request, response: Response, asset: str):
    def fetch():
        try:
            fx = FX(asset)
            info = fx.current
            if not info:
                return {"error": f"Asset {asset} not found or unavailable"}
            return compact_payload({k: clean_json_val(v) for k, v in info.items()})
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_realtime(f"FX_{asset}", fetch)


@router.get("/{asset}/history")
@limiter.limit("30/minute")
def get_fx_history(request: Request, response: Response, asset: str, period: str = "1mo", interval: str = "1d"):
    def fetch():
        try:
            fx = FX(asset)
            df = fx.history(period=period, interval=interval)
            if df.empty:
                return {"error": "No historical data available"}
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_realtime(f"FX_HIST_{asset}_{period}_{interval}", fetch)


@router.get("/{asset}/bank-rates")
@limiter.limit("20/minute")
def get_fx_bank_rates(request: Request, response: Response, asset: str):
    def fetch():
        try:
            fx = FX(asset)
            df = fx.bank_rates
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"FX_BANKS_{asset}", fetch)


@router.get("/{asset}/bank-rate/{bank}")
@limiter.limit("20/minute")
def get_fx_bank_rate_detail(request: Request, response: Response, asset: str, bank: str):
    def fetch():
        try:
            fx = FX(asset)
            rate = fx.bank_rate(bank)
            return compact_payload({k: clean_json_val(v) for k, v in rate.items()})
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"FX_BANK_DETAIL_{asset}_{bank}", fetch)


@router.get("/{asset}/institution-rates")
@limiter.limit("20/minute")
def get_fx_institution_rates(request: Request, response: Response, asset: str):
    def fetch():
        try:
            fx = FX(asset)
            df = fx.institution_rates
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"FX_INSTITUTIONS_{asset}", fetch)


@router.get("/{asset}/institution-rate/{institution}")
@limiter.limit("20/minute")
def get_fx_institution_rate_detail(request: Request, response: Response, asset: str, institution: str):
    def fetch():
        try:
            fx = FX(asset)
            rate = fx.institution_rate(institution)
            return compact_payload({k: clean_json_val(v) for k, v in rate.items()})
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"FX_INSTITUTION_DETAIL_{asset}_{institution}", fetch)


@router.get("/{asset}/institution-history")
@limiter.limit("20/minute")
def get_fx_institution_history(request: Request, response: Response, asset: str, institution: str, period: str = "1mo"):
    def fetch():
        try:
            fx = FX(asset)
            df = fx.institution_history(institution=institution, period=period)
            if df.empty:
                return {"error": "No institution history data available"}
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_realtime(f"FX_INST_HIST_{asset}_{institution}_{period}", fetch)

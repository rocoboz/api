from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from api_core.services.cache import get_cached_market, get_cached_static
from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json
from api_core.services.response import api_ok
from api_core.services.security import limiter
from borsapy import Bond, bonds, risk_free_rate, Eurobond, eurobonds

router = APIRouter(tags=["bonds"])


@router.get("/bonds/list")
@limiter.limit("20/minute")
def get_bonds_list(request: Request, response: Response, envelope: bool = False):
    def fetch():
        try:
            return df_to_json(bonds())
        except Exception:
            return []

    data = get_cached_static("BONDS_LIST", fetch)
    return api_ok(data) if envelope else data


@router.get("/bonds/risk-free-rate")
@limiter.limit("20/minute")
def get_bond_rfr(request: Request, response: Response, envelope: bool = False):
    def fetch():
        try:
            val = risk_free_rate()
            return {"risk_free_rate": clean_json_val(val)}
        except Exception as exc:
            return {"error": str(exc)}

    data = get_cached_static("BONDS_RFR", fetch)
    return api_ok(data) if envelope else data


@router.get("/bonds/{maturity}")
@limiter.limit("30/minute")
def get_bond_detail(request: Request, response: Response, maturity: str):
    maturity = maturity.upper()
    if maturity not in Bond.MATURITIES:
        return {"error": f"Invalid maturity '{maturity}'. Valid options: 2Y, 5Y, 10Y"}

    def fetch():
        try:
            b = Bond(maturity)
            return compact_payload({k: clean_json_val(v) for k, v in b.info.items()})
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_static(f"BOND_{maturity}", fetch)


@router.get("/eurobonds/list")
@limiter.limit("20/minute")
def get_eurobonds_list(request: Request, response: Response, currency: str | None = Query(None), envelope: bool = False):
    def fetch():
        try:
            df = eurobonds(currency=currency)
            return df_to_json(df)
        except Exception:
            return []

    data = get_cached_static(f"EUROBONDS_LIST_{currency}", fetch)
    return api_ok(data) if envelope else data


@router.get("/eurobonds/{isin}")
@limiter.limit("30/minute")
def get_eurobond_detail(request: Request, response: Response, isin: str):
    isin = isin.upper()

    def fetch():
        try:
            eb = Eurobond(isin)
            info = eb.info
            # Convert maturity datetime to string
            if "maturity" in info and info["maturity"]:
                info["maturity"] = info["maturity"].isoformat()
            return compact_payload({k: clean_json_val(v) for k, v in info.items()})
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_static(f"EUROBOND_{isin}", fetch)


@router.get("/eurobonds/{isin}/history")
@limiter.limit("15/minute")
def get_eurobond_history(request: Request, response: Response, isin: str, period: str = "1y"):
    isin = isin.upper()

    def fetch():
        try:
            eb = Eurobond(isin)
            df = eb.history(period=period)
            if df.empty:
                return {"error": "No historical Eurobond data available"}
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"EUROBOND_HIST_{isin}_{period}", fetch)

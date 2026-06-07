from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Query, Request, Response

from api_core.services.cache import get_cached_market, get_cached_static
from api_core.services.enrichers import enrich_stock_rows
from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json, normalize_fund_row
from api_core.services.providers import Index, clear_twitter_auth, market, search_funds, search_tweets, set_twitter_auth
from api_core.services.response import api_ok
from api_core.services.security import limiter, verify_api_key

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/tweets", dependencies=[Depends(verify_api_key)])
@limiter.limit("5/minute")
def twitter_search(request: Request, response: Response, q: str, limit: int = 15):
    def fetch():
        try:
            env_token = os.getenv("TWITTER_AUTH_TOKEN")
            env_ct0 = os.getenv("TWITTER_CT0")
            if env_token and env_ct0:
                set_twitter_auth(auth_token=env_token, ct0=env_ct0)
            else:
                return {"error": "Twitter authentication required on server environment."}
            results = df_to_json(search_tweets(q, limit=limit))
            set_twitter_auth(auth_token=env_token, ct0=env_ct0)
            return results
        except Exception as exc:
            return {"error": f"Twitter Search Failed: {exc}"}
        finally:
            if not (env_token and env_ct0):
                clear_twitter_auth()

    return get_cached_market(f"TWEETS_{q}_{limit}", fetch)


@router.get("")
@limiter.limit("30/minute")
def unified_search(request: Request, response: Response, q: str, envelope: bool = False):
    def fetch():
        try:
            stocks = market.search_companies(q)
            funds = search_funds(q, limit=10)
            st_res = enrich_stock_rows(df_to_json(stocks.head(10)))
            f_res = [compact_payload(normalize_fund_row(row)) for row in df_to_json(funds)]
            indexes = []
            try:
                for code in ["XU100", "XBANK", "XUSIN"]:
                    if q.upper() in code:
                        idx = Index(code)
                        indexes.append(
                            compact_payload(
                                {
                                    "symbol": code,
                                    "name": idx.info.get("short_name", code),
                                    "price": clean_json_val(idx.info.get("last_price")),
                                    "change": clean_json_val(idx.info.get("change_percent")),
                                }
                            )
                        )
            except Exception:
                pass
            return compact_payload({"stocks": st_res, "funds": f_res, "indexes": indexes, "total": len(st_res) + len(f_res) + len(indexes)})
        except Exception:
            return {"stocks": [], "funds": [], "indexes": [], "total": 0}

    payload = get_cached_static(f"SEARCH_{q}", fetch)
    return api_ok(payload, {"query": q, "count": payload.get("total", 0)}) if envelope else payload

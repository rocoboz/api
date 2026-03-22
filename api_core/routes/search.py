from __future__ import annotations

import os

from fastapi import APIRouter, Query, Response

from api_core.services.cache import get_cached_market, get_cached_static
from api_core.services.enrichers import enrich_stock_rows
from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json, normalize_fund_row
from api_core.services.providers import Index, clear_twitter_auth, market, search_funds, search_tweets, set_twitter_auth
from api_core.services.response import api_ok

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/tweets")
def twitter_search(q: str, limit: int = 15, auth_token: str | None = Query(None), ct0: str | None = Query(None)):
    def fetch():
        try:
            env_token = os.getenv("TWITTER_AUTH_TOKEN")
            env_ct0 = os.getenv("TWITTER_CT0")
            if auth_token and ct0:
                set_twitter_auth(auth_token=auth_token, ct0=ct0)
            elif env_token and env_ct0:
                set_twitter_auth(auth_token=env_token, ct0=env_ct0)
            else:
                return {"error": "Twitter authentication required. Please provide auth_token and ct0 parameters."}
            results = df_to_json(search_tweets(q, limit=limit))
            if env_token and env_ct0:
                set_twitter_auth(auth_token=env_token, ct0=env_ct0)
            else:
                clear_twitter_auth()
            return results
        except Exception as exc:
            return {"error": f"Twitter Search Failed: {exc}"}

    return get_cached_market(f"TWEETS_{q}_{limit}", fetch)


@router.get("")
def unified_search(response: Response, q: str, envelope: bool = False):
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

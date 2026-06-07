from __future__ import annotations

import os
from fastapi import APIRouter, Query, Request, Response

from api_core.services.cache import get_cached_market, get_cached_static
from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json
from api_core.services.response import api_ok
from api_core.services.security import limiter
from borsapy import EVDS, EVDSSeries, evds_categories, evds_download, evds_search, set_evds_key

router = APIRouter(prefix="/evds", tags=["evds"])

# Initialize EVDS key on startup if provided via environment
env_evds_key = os.getenv("EVDS_KEY")
if env_evds_key:
    set_evds_key(env_evds_key)


@router.get("/categories")
@limiter.limit("20/minute")
def get_evds_categories(request: Request, response: Response, envelope: bool = False):
    def fetch():
        try:
            return df_to_json(evds_categories())
        except Exception:
            return []

    data = get_cached_static("EVDS_CATEGORIES", fetch)
    return api_ok(data) if envelope else data


@router.get("/search")
@limiter.limit("20/minute")
def search_evds(request: Request, response: Response, q: str, lang: str = "tr", scope: str = "all", envelope: bool = False):
    def fetch():
        try:
            return df_to_json(evds_search(q, lang=lang, scope=scope))
        except Exception:
            return []

    data = get_cached_static(f"EVDS_SEARCH_{q}_{lang}_{scope}", fetch)
    return api_ok(data) if envelope else data


@router.get("/datagroups")
@limiter.limit("20/minute")
def get_evds_datagroups(request: Request, response: Response, category_id: int | None = Query(None), envelope: bool = False):
    def fetch():
        try:
            ev = EVDS()
            return df_to_json(ev.datagroups(category_id=category_id))
        except Exception:
            return []

    data = get_cached_static(f"EVDS_DATAGROUPS_{category_id}", fetch)
    return api_ok(data) if envelope else data


@router.get("/series")
@limiter.limit("20/minute")
def get_evds_series_in_group(request: Request, response: Response, datagroup_code: str, envelope: bool = False):
    def fetch():
        try:
            ev = EVDS()
            return df_to_json(ev.series_in_group(datagroup_code))
        except Exception:
            return []

    data = get_cached_static(f"EVDS_SERIES_GROUP_{datagroup_code}", fetch)
    return api_ok(data) if envelope else data


@router.get("/series/{code}")
@limiter.limit("30/minute")
def get_evds_series_detail(request: Request, response: Response, code: str):
    def fetch():
        try:
            s = EVDSSeries(code)
            info = s.info
            # Convert pandas timestamp bounds to string
            start_date, end_date = s.range
            info["start_date"] = start_date.isoformat() if start_date else None
            info["end_date"] = end_date.isoformat() if end_date else None
            return compact_payload({k: clean_json_val(v) for k, v in info.items()})
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_static(f"EVDS_SERIES_{code}", fetch)


@router.get("/series/{code}/history")
@limiter.limit("30/minute")
def get_evds_series_history(request: Request, response: Response, code: str, period: str = "1y", frequency: str | None = Query(None)):
    def fetch():
        try:
            s = EVDSSeries(code)
            df = s.history(period=period, frequency=frequency)
            if df.empty:
                return {"error": "No data found"}
            # Index is Date, columns are Value or code. Reset index to serialize Date
            df_reset = df.reset_index()
            return df_to_json(df_reset)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"EVDS_SERIES_HIST_{code}_{period}_{frequency}", fetch)


@router.get("/download")
@limiter.limit("15/minute")
def get_evds_download(request: Request, response: Response, codes: str, period: str = "1y", frequency: str = "monthly", envelope: bool = False):
    code_list = [c.strip() for c in codes.split(",") if c.strip()]

    def fetch():
        try:
            df = evds_download(code_list, period=period, frequency=frequency)
            if df.empty:
                return []
            df_reset = df.reset_index()
            return df_to_json(df_reset)
        except Exception:
            return []

    data = get_cached_market(f"EVDS_DOWNLOAD_{codes}_{period}_{frequency}", fetch)
    return api_ok(data) if envelope else data


@router.get("/dashboard")
@limiter.limit("20/minute")
def get_evds_dashboard(request: Request, response: Response, slug: str = "baslica-gostergeler"):
    def fetch():
        try:
            ev = EVDS()
            return compact_payload(ev.dashboard(slug))
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"EVDS_DASHBOARD_{slug}", fetch)


@router.get("/announcements")
@limiter.limit("20/minute")
def get_evds_announcements(request: Request, response: Response, envelope: bool = False):
    def fetch():
        try:
            ev = EVDS()
            return ev.announcements()
        except Exception:
            return []

    data = get_cached_static("EVDS_ANNOUNCEMENTS", fetch)
    return api_ok(data) if envelope else data

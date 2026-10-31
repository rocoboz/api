from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends

from api_core.services.cache import cache_overview, get_cached_market
from api_core.services.response import api_ok
from api_core.services.security import verify_api_key

router = APIRouter(prefix="/ops", tags=["ops"])

# Reachability probes. Render runs behind a foreign outbound IP, so Turkish
# public institutions may answer 403/429 even when the service itself is up.
# Each probe reports the HTTP status and what the failure would break.
PROVIDER_PROBES: list[dict[str, Any]] = [
    {
        "provider": "canlidoviz",
        "role": "Döviz, altın, gümüş, platin kotasyonları ve geçmiş",
        "url": "https://a.canlidoviz.com/items/history",
        "params": {
            "period": "DAILY",
            "itemDataId": 1,
            "startDate": "2026-01-01T00:00:00",
            "endDate": "2026-01-05T23:59:59",
        },
        "headers": {
            "Origin": "https://canlidoviz.com",
            "Referer": "https://canlidoviz.com/",
        },
        "expect_json": True,
    },
    {
        "provider": "doviz.com",
        "role": "Banka kurları ve kuyumcu fiyatları",
        "url": "https://www.doviz.com/",
        "expect_text": "doviz",
    },
    {
        "provider": "tcmb",
        "role": "Resmî döviz kurları",
        "url": "https://www.tcmb.gov.tr/kurlar/today.xml",
        "expect_text": "<Currency",
    },
    {
        "provider": "evds",
        "role": "Resmî veri setleri (enflasyon, faiz, döviz serileri)",
        "url": "https://evds3.tcmb.gov.tr/",
        "requires_env": ("EVDS_API_KEY", "EVDS_KEY"),
    },
    {
        "provider": "tefas",
        "role": "Yatırım fonu fiyatları",
        "url": "https://www.tefas.gov.tr/",
    },
    {
        "provider": "tradingview",
        "role": "BIST hisse fiyatları, taramalar ve intraday grafikler",
        "url": "https://www.tradingview.com/",
    },
    {
        "provider": "btcturk",
        "role": "Kripto varlık fiyatları",
        "url": "https://api.btcturk.com/api/v2/ticker",
        "params": {"pair": "BTCTRY"},
        "expect_json": True,
    },
    {
        "provider": "kap",
        "role": "Şirket bildirimleri ve fon portföy dağılımı",
        "url": "https://www.kap.org.tr/tr",
    },
    {
        "provider": "borsa-istanbul",
        "role": "Endeks bileşenleri",
        "url": "https://www.borsaistanbul.com/datum/hisse_endeks_ds.csv",
    },
]


def _classify(response: httpx.Response, probe: dict[str, Any]) -> tuple[str, str | None]:
    status = response.status_code
    if status in (403, 429, 451):
        return "blocked", f"HTTP {status}: kaynak isteği reddetti"
    if status >= 400:
        return "error", f"HTTP {status}"

    if probe.get("expect_json"):
        try:
            payload = response.json()
        except Exception:
            return "error", "Yanıt JSON değil"
        if not payload:
            return "error", "Boş yanıt"
    if probe.get("expect_text"):
        if probe["expect_text"].lower() not in response.text.lower():
            return "error", "Beklenen içerik bulunamadı"
    return "ok", None


def _probe(probe: dict[str, Any]) -> dict[str, Any]:
    requires_env = probe.get("requires_env") or ()
    if requires_env and not any(os.getenv(name) for name in requires_env):
        return {
            "provider": probe["provider"],
            "role": probe["role"],
            "status": "missing_key",
            "detail": f"Ortam değişkeni tanımlı değil: {', '.join(requires_env)}",
        }

    started = time.perf_counter()
    try:
        # TCMB regularly answers in 8-10 seconds even when healthy, so the
        # probe budget is larger than the per-provider timeout used for data
        # endpoints.  Probes run in parallel.
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            response = client.get(
                probe["url"],
                params=probe.get("params"),
                headers=probe.get("headers"),
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        status, detail = _classify(response, probe)
        return {
            "provider": probe["provider"],
            "role": probe["role"],
            "status": status,
            "http_status": response.status_code,
            "latency_ms": latency_ms,
            "detail": detail,
        }
    except httpx.TimeoutException:
        return {
            "provider": probe["provider"],
            "role": probe["role"],
            "status": "timeout",
            "detail": "12 saniye içinde yanıt alınamadı",
        }
    except Exception as exc:
        return {
            "provider": probe["provider"],
            "role": probe["role"],
            "status": "error",
            "detail": str(exc),
        }


@router.get("/cache", dependencies=[Depends(verify_api_key)])
def cache_stats():
    return api_ok(cache_overview())


@router.get("/providers")
def provider_diagnostics():
    """Check upstream reachability from the machine that serves this request."""

    def fetch():
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(_probe, probe) for probe in PROVIDER_PROBES]
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:  # pragma: no cover - defensive
                    results.append({"provider": "bilinmeyen", "status": "error", "detail": str(exc)})

        order = {probe["provider"]: index for index, probe in enumerate(PROVIDER_PROBES)}
        results.sort(key=lambda item: order.get(item["provider"], 999))
        counts: dict[str, int] = {}
        for item in results:
            counts[item["status"]] = counts.get(item["status"], 0) + 1

        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "environment": "render" if os.getenv("RENDER") else "local",
            "summary": counts,
            "providers": results,
        }

    return get_cached_market("OPS_PROVIDERS", fetch)


@router.api_route("/health", methods=["GET", "HEAD"])
def health():
    return api_ok({"status": "healthy"})


@router.api_route("/ready", methods=["GET", "HEAD"])
def ready():
    return api_ok({"status": "ready"})

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx

API_BASE_URL = os.getenv("API_BASE_URL")
HEADERS = {"x-api-key": os.getenv("API_KEY", "OPEN")}

if API_BASE_URL:
    CLIENT_MODE = "remote"
    client = httpx.Client(base_url=API_BASE_URL, headers=HEADERS, timeout=45.0)
else:
    CLIENT_MODE = "in-process"
    sys.path.append(r"D:\vibecodding\api\borsapy-api")
    from fastapi.testclient import TestClient
    import main

    client = TestClient(main.app)

ENDPOINTS = [
    ("Ping", "/ping"),
    ("Home", "/"),
    ("Cache Stats", "/ops/cache"),
    ("Health", "/ops/health"),
    ("Ready", "/ops/ready"),
    ("Stocks List", "/stocks/list?limit=3&offset=0"),
    ("Stocks List Envelope", "/stocks/list?limit=3&offset=0&envelope=true"),
    ("Stock Detail", "/stocks/THYAO"),
    ("Stock History", "/stocks/THYAO/history?period=1mo&interval=1d"),
    ("Stock Depth", "/stocks/THYAO/depth"),
    ("Stock Disclosures", "/stocks/THYAO/disclosures?limit=3"),
    ("Stock Compare", "/stocks/compare?symbols=THYAO,ASELS"),
    ("Market Screener", "/market/screener?limit=3&offset=0"),
    ("Stock Dividends", "/stocks/THYAO/dividends"),
    ("Stock Financials", "/stocks/THYAO/financials?type=income"),
    ("Technical Analysis", "/analysis/THYAO"),
    ("Sentiment Analysis", "/analysis/THYAO/sentiment"),
    ("Hybrid Insight", "/analysis/THYAO/insight"),
    ("Funds List", "/funds/list?limit=3&offset=0"),
    ("Funds List Envelope", "/funds/list?limit=3&offset=50&envelope=true"),
    ("Fund Detail", "/funds/TLY"),
    ("Fund History", "/funds/TLY/history?period=1mo"),
    ("Fund Estimate", "/funds/TLY/estimated-return"),
    ("Fund Screener", "/funds/screener?fund_type=YAT"),
    ("Market Breadth", "/market/breadth"),
    ("Market Heatmap", "/market/heatmap"),
    ("Market Summary", "/market/summary"),
    ("Home Highlights", "/home/highlights"),
    ("TCMB Rates", "/market/economy/rates"),
    ("Economic Calendar", "/market/economy/calendar?scope=today"),
    ("VIOP List", "/viop/list?category=all"),
    ("Inflation", "/market/economy/inflation"),
    ("Tax Table", "/market/tax"),
    ("Twitter Search", "/search/tweets?q=THYAO&limit=2"),
    ("Unified Search", "/search?q=THYAO"),
    ("Unified Search Envelope", "/search?q=THYAO&envelope=true"),
]

EXPECTED_AUTH_FAILURES = {"Cache Stats", "Twitter Search"}


def summarize(payload: Any) -> Any:
    if isinstance(payload, dict):
        if payload.get("error"):
            return {"error": payload["error"]}
        return {key: summarize(value) for key, value in list(payload.items())[:5]}
    if isinstance(payload, list):
        return {"len": len(payload), "first": summarize(payload[0]) if payload else None}
    return payload


def null_count(payload: Any) -> int:
    if payload is None:
        return 1
    if isinstance(payload, dict):
        return sum(null_count(value) for value in payload.values())
    if isinstance(payload, list):
        return sum(null_count(value) for value in payload)
    return 0


def _get(path: str):
    return client.get(path)


def run_tests() -> int:
    failures = 0
    target = API_BASE_URL or "in-process TestClient"
    print(f"Testing {target} ({CLIENT_MODE})\n")

    for name, path in ENDPOINTS:
        started = time.time()
        try:
            response = _get(path)
            elapsed = round(time.time() - started, 2)
            content_type = response.headers.get("content-type", "")
            body = response.json() if "application/json" in content_type else response.text
            top_error = body.get("error") if isinstance(body, dict) else None
            nulls = null_count(body)

            print(f"[{response.status_code}] {name} ({elapsed}s)")
            print(json.dumps(summarize(body), ensure_ascii=False)[:1000])
            print(f"null_count={nulls}")

            if response.status_code >= 400 and not (response.status_code == 403 and name in EXPECTED_AUTH_FAILURES):
                failures += 1
            elif top_error and name not in {"Twitter Search", "Sentiment Analysis"}:
                failures += 1
            print("---")
        except Exception as exc:
            failures += 1
            print(f"[ERR] {name}: {exc}")
            print("---")

    print(f"Failures: {failures}")
    return failures


def run_concurrency_smoke() -> int:
    paths = [
        "/market/summary",
        "/market/screener?limit=5&offset=0",
        "/funds/list?limit=50&offset=0",
        "/stocks/THYAO/history?period=1mo&interval=1d",
    ]
    failures = 0
    started = time.time()
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(_get, paths[index % len(paths)]) for index in range(48)]
        for future in as_completed(futures):
            try:
                response = future.result()
                if response.status_code >= 400:
                    failures += 1
            except Exception:
                failures += 1
    elapsed = round(time.time() - started, 2)
    print(f"Concurrency smoke finished in {elapsed}s with {failures} failures")
    return failures


if __name__ == "__main__":
    failures = run_tests()
    failures += run_concurrency_smoke()
    sys.exit(failures)

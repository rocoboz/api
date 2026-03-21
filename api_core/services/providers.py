from __future__ import annotations

import os
import re
import sys
from typing import Any

import httpx

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
lib_path = os.path.join(base_dir, "borsapy_lib")
if os.path.exists(lib_path) and lib_path not in sys.path:
    sys.path.append(lib_path)

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None

from borsapy import (  # type: ignore
    Bond,
    Crypto,
    EconomicCalendar,
    Eurobond,
    FX,
    Fund,
    Index,
    Inflation,
    Portfolio,
    TCMB,
    Ticker,
    VIOP,
    market,
    screener,
    search_funds,
    search_tweets,
    screen_funds,
    set_twitter_auth,
    clear_twitter_auth,
    tax,
    technical,
)
from borsapy._providers.kap import get_kap_provider  # type: ignore


def parse_fund_holdings_no_llm(fund_code: str):
    """Scrape KAP for the latest PDR PDF and extract stock weights via regex."""
    fund_code = fund_code.upper()
    try:
        tefas = Fund(fund_code)
        kap_url = tefas.info.get("kap_link")
        if not kap_url or fitz is None:
            return None

        resp = httpx.get(kap_url, timeout=10)
        oids = re.findall(r"([a-fA-F0-9]{32})", resp.text)
        if not oids:
            return None

        pdr_type = "8aca490d502e34b801502e380044002b"
        disclosures = None
        print(f"DEBUG: Found {len(set(oids))} potential OIDs for {fund_code}")
        for fund_oid in set(oids):
            try:
                filter_url = f"https://kap.org.tr/tr/api/disclosure/filter/FILTERYFBF/{fund_oid}/{pdr_type}/365"
                f_resp = httpx.get(filter_url, timeout=5)
                if f_resp.status_code == 200:
                    data = f_resp.json()
                    if data:
                        print(f"DEBUG: Found valid OID: {fund_oid}")
                        disclosures = data
                        break
            except Exception:
                continue

        if not disclosures:
            print(f"DEBUG: No PDR disclosures found for {fund_code}")
            return None

        latest_idx = disclosures[0]["disclosureBasic"]["disclosureIndex"]
        print(f"DEBUG: Latest PDR Index: {latest_idx}")

        disc_page = f"https://www.kap.org.tr/tr/Bildirim/{latest_idx}"
        resp = httpx.get(disc_page, timeout=10)
        file_id_match = re.search(r"file/download/([a-f0-9]{32})", resp.text)
        if not file_id_match:
            print(f"DEBUG: File ID not found in disclosure {latest_idx}")
            return None

        file_id = file_id_match.group(1)
        print(f"DEBUG: Downloading PDF {file_id}")
        pdf_url = f"https://kap.org.tr/tr/api/file/download/{file_id}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = httpx.get(pdf_url, headers=headers, timeout=30)
        data = resp.content
        pdf_start = data.find(b"%PDF-")
        if pdf_start == -1:
            print(f"DEBUG: Valid PDF header not found for {fund_code}")
            return None

        pdf_data = data[pdf_start:]
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        print(f"DEBUG: PDF text extracted, length: {len(text)}")

        print("DEBUG: Starting Regex scan for holdings...")
        unique_stocks: dict[str, float] = {}
        try:
            bist_tickers = set(market.companies()["ticker"].tolist())
        except Exception:
            bist_tickers = set()

        for match in re.finditer(r"\n([A-Z]{4,5})\s*\n", text):
            sym = match.group(1)
            if bist_tickers and sym not in bist_tickers:
                continue
            sym_pos = match.end()
            search_window = text[sym_pos : sym_pos + 300]
            weight_match = re.search(r"(\d+,\d{2})\s*\n\s*(\d+,\d{2})\s*\n\s*(?:TL|TRY|USD|EUR)", search_window)
            if weight_match:
                val = weight_match.group(2)
            else:
                nums = re.findall(r"(\d+,\d{2})", search_window)
                val = next((n for n in reversed(nums) if 0.01 <= float(n.replace(",", ".")) <= 40.0), None)
            if not val:
                continue
            try:
                weight = float(val.replace(",", "."))
                if 0.05 <= weight <= 40:
                    unique_stocks[sym] = max(unique_stocks.get(sym, 0), weight)
            except Exception:
                continue

        return [{"symbol": symbol, "weight": weight} for symbol, weight in unique_stocks.items()]
    except Exception as exc:
        print(f"Deep Parsing Error for {fund_code}: {exc}")
        return None

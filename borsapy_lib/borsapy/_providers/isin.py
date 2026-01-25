"""ISIN (International Securities Identification Number) provider."""

import re
import time

from borsapy._providers.base import BaseProvider
from borsapy._providers.kap import get_kap_provider


class ISINProvider(BaseProvider):
    """
    Provider for ISIN codes from isinturkiye.com.tr.

    ISIN codes are unique 12-character identifiers for securities,
    standardized by ISO 6166.

    Uses a 3-step lookup:
    1. Get company name from KAP (ticker → company name)
    2. Find ihracKod by fuzzy matching in ISIN Turkey (company name → ihracKod)
    3. Get ISIN from ihracKod (ihracKod → ISIN)

    Example: THYAO → "TÜRK HAVA YOLLARI A.O." → THYA → TRATHYAO91M5
    """

    ISIN_API_URL = "https://www.isinturkiye.com.tr/v17/tvs/isin/portal/bff/tvs/isin/portal/public/isinListele"
    COMPANY_LIST_URL = "https://www.isinturkiye.com.tr/v17/tvs/isin/portal/bff/tvs/isin/portal/public/isinSirketListe"
    CACHE_DURATION = 86400 * 7  # 7 days (ISIN codes rarely change)
    COMPANY_CACHE_DURATION = 86400  # 24 hours for company list

    def __init__(self):
        super().__init__()
        self._isin_companies: list[dict] | None = None
        self._isin_companies_time: float = 0

    def get_isin(self, symbol: str) -> str | None:
        """
        Get ISIN code for a stock symbol.

        Args:
            symbol: Stock symbol (e.g., "THYAO", "GARAN").

        Returns:
            ISIN code string (e.g., "TRATHYAO91M5") or None if not found.
        """
        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        # Check cache first
        cache_key = f"isin_{symbol}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            # Step 1: Get company name from KAP
            company_name = self._get_company_name(symbol)
            if not company_name:
                return None

            # Step 2: Find ihracKod by fuzzy matching
            ihrac_kod = self._find_ihrac_kod(company_name)
            if not ihrac_kod:
                return None

            # Step 3: Get ISIN from ihracKod
            isin = self._get_isin_from_ihrac(ihrac_kod, symbol)
            if isin:
                self._cache_set(cache_key, isin, self.CACHE_DURATION)
                return isin

            return None

        except Exception:
            return None

    def _get_company_name(self, symbol: str) -> str | None:
        """
        Get company name from KAP for a stock symbol.

        Args:
            symbol: Stock symbol.

        Returns:
            Company name or None.
        """
        try:
            kap = get_kap_provider()
            companies_df = kap.get_companies()
            result = companies_df[companies_df["ticker"] == symbol.upper()]
            if not result.empty:
                return result.iloc[0]["name"]
        except Exception:
            pass
        return None

    def _get_isin_companies(self) -> list[dict]:
        """
        Get and cache the ISIN Turkey company list.

        Returns:
            List of company dictionaries with srkKod and srkAd.
        """
        current_time = time.time()

        if (
            self._isin_companies is not None
            and (current_time - self._isin_companies_time) < self.COMPANY_CACHE_DURATION
        ):
            return self._isin_companies

        try:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://www.isinturkiye.com.tr",
                "Referer": "https://www.isinturkiye.com.tr/v17/tvs/isin/portal/bff/index.html",
            }

            response = self._client.post(
                self.COMPANY_LIST_URL,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            self._isin_companies = data.get("resultList", [])
            self._isin_companies_time = current_time
            return self._isin_companies

        except Exception:
            return []

    def _normalize_text(self, text: str) -> str:
        """Normalize Turkish text for comparison."""
        text = text.upper()
        tr_map = {"İ": "I", "Ş": "S", "Ğ": "G", "Ü": "U", "Ö": "O", "Ç": "C"}
        for k, v in tr_map.items():
            text = text.replace(k, v)
        return re.sub(r"[.,\-'\"\s]+", " ", text).strip()

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract meaningful keywords from company name."""
        text = self._normalize_text(text)
        stopwords = {
            "VE", "A", "AS", "AO", "TAS", "ANONIM", "SIRKETI", "SIRKET",
            "TURKIYE", "TURK", "HOLDING", "SANAYI", "TICARET",
        }
        return {w for w in text.split() if w not in stopwords and len(w) > 2}

    def _find_ihrac_kod(self, company_name: str) -> str | None:
        """
        Find ihracKod by fuzzy matching company name in ISIN Turkey.

        Args:
            company_name: Company name from KAP.

        Returns:
            ihracKod or None.
        """
        companies = self._get_isin_companies()
        if not companies:
            return None

        company_keywords = self._extract_keywords(company_name)
        if not company_keywords:
            return None

        best_match = None
        best_score = 0

        for c in companies:
            srk_ad = c.get("srkAd", "")
            # Extract company name part (after "CODE - ")
            srk_name = srk_ad.split(" - ", 1)[1] if " - " in srk_ad else srk_ad
            srk_keywords = self._extract_keywords(srk_name)

            if srk_keywords:
                common = company_keywords.intersection(srk_keywords)
                score = len(common) / max(len(company_keywords), len(srk_keywords))

                if score > best_score:
                    best_score = score
                    best_match = c.get("srkKod")

        # Return if score is good enough (>0.35)
        return best_match if best_score > 0.35 else None

    def _get_isin_from_ihrac(self, ihrac_kod: str, symbol: str) -> str | None:
        """
        Get ISIN code from ihracKod.

        Args:
            ihrac_kod: Issuer code (e.g., "THYA").
            symbol: Stock symbol to match (e.g., "THYAO").

        Returns:
            ISIN code or None.
        """
        try:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://www.isinturkiye.com.tr",
                "Referer": "https://www.isinturkiye.com.tr/v17/tvs/isin/portal/bff/index.html",
            }

            payload = {
                "isinKod": "",
                "ihracKod": ihrac_kod,
                "kategori": "",
                "menkulTurKod": "",
            }

            response = self._client.post(
                self.ISIN_API_URL,
                json=payload,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            # Find matching stock (PAY type with matching borsaKodu)
            for item in data.get("resultList", []):
                borsa_kodu = item.get("borsaKodu", "").split(" - ")[0].strip()
                menkul_tur = item.get("menkulTur", "")
                isin = item.get("isinKod", "")

                if borsa_kodu == symbol and ("PAY" in menkul_tur or "Hisse" in menkul_tur):
                    return isin

            return None

        except Exception:
            return None


# Singleton
_provider: ISINProvider | None = None


def get_isin_provider() -> ISINProvider:
    """Get singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = ISINProvider()
    return _provider

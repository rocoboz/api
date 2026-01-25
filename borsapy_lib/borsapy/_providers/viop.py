"""VİOP provider for derivatives data via İş Yatırım HTML scraping."""

import pandas as pd
from bs4 import BeautifulSoup

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL
from borsapy.exceptions import APIError

# Singleton instance
_viop_provider: "ViOpProvider | None" = None


def get_viop_provider() -> "ViOpProvider":
    """Get singleton VİOP provider instance."""
    global _viop_provider
    if _viop_provider is None:
        _viop_provider = ViOpProvider()
    return _viop_provider


class ViOpProvider(BaseProvider):
    """
    Provider for VİOP (Vadeli İşlem ve Opsiyon Piyasası) data.

    Data source: İş Yatırım VİOP page (HTML scraping)
    Note: Data is delayed by ~15 minutes (Matriks source)
    """

    URL = "https://www.isyatirim.com.tr/tr-tr/analiz/Sayfalar/viop.aspx"

    # Table section identifiers (Turkish)
    SECTIONS = {
        "stock_futures": "Pay Vadeli İşlem Ana Pazarı",
        "index_futures": "Endeks Vadeli İşlem Ana Pazarı",
        "currency_futures": "Döviz Vadeli İşlem Ana Pazarı",
        "commodity_futures": "Kıymetli Madenler Vadeli İşlem Ana Pazarı",
        "stock_options": "Pay Opsiyon Ana Pazarı",
        "index_options": "Endeks Opsiyon Ana Pazarı",
    }

    def _fetch_page(self) -> BeautifulSoup:
        """Fetch and parse VİOP page."""
        cache_key = "viop:page"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            response = self._get(self.URL)
            soup = BeautifulSoup(response.text, "html.parser")
            self._cache_set(cache_key, soup, TTL.VIOP)
            return soup
        except Exception as e:
            raise APIError(f"Failed to fetch VİOP page: {e}") from e

    def _parse_table(self, soup: BeautifulSoup, section_name: str) -> pd.DataFrame:
        """Parse a VİOP table section."""
        # Find accordion with the section name
        accordion = None
        for a_tag in soup.find_all("a"):
            if a_tag.get_text(strip=True) == section_name:
                accordion = a_tag.find_parent("div", class_="accordion-item")
                break

        if accordion is None:
            return pd.DataFrame()

        # Find table within accordion
        table = accordion.find("table")
        if table is None:
            return pd.DataFrame()

        rows = []
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 5:
                # Extract contract code from title attribute
                first_td = tds[0]
                title = first_td.get("title", "")
                contract_code = ""
                if "|" in title:
                    contract_code = title.split("|")[0].strip()

                contract_name = first_td.get_text(strip=True)
                price = self._parse_number(tds[1].get_text(strip=True))
                change = self._parse_number(tds[2].get_text(strip=True))
                volume_tl = self._parse_number(tds[3].get_text(strip=True))
                volume_qty = self._parse_number(tds[4].get_text(strip=True))

                rows.append({
                    "code": contract_code,
                    "contract": contract_name,
                    "price": price,
                    "change": change,
                    "volume_tl": volume_tl,
                    "volume_qty": volume_qty,
                })

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)

    def _parse_number(self, text: str) -> float | None:
        """Parse Turkish number format (1.234,56 -> 1234.56)."""
        if not text:
            return None
        try:
            # Remove thousand separator (.) and convert decimal separator (,) to (.)
            cleaned = text.replace(".", "").replace(",", ".")
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def get_futures(self, category: str = "all") -> pd.DataFrame:
        """
        Get futures contracts.

        Args:
            category: Filter by category:
                - "all": All futures
                - "stock": Stock futures (Pay Vadeli)
                - "index": Index futures (Endeks Vadeli)
                - "currency": Currency futures (Döviz Vadeli)
                - "commodity": Commodity futures (Kıymetli Madenler)

        Returns:
            DataFrame with columns: code, contract, price, change, volume_tl, volume_qty
        """
        soup = self._fetch_page()

        category_map = {
            "stock": ["stock_futures"],
            "index": ["index_futures"],
            "currency": ["currency_futures"],
            "commodity": ["commodity_futures"],
            "all": ["stock_futures", "index_futures", "currency_futures", "commodity_futures"],
        }

        sections = category_map.get(category, category_map["all"])
        dfs = []

        for section_key in sections:
            section_name = self.SECTIONS.get(section_key)
            if section_name:
                df = self._parse_table(soup, section_name)
                if not df.empty:
                    df["category"] = section_key.replace("_futures", "")
                    dfs.append(df)

        if not dfs:
            return pd.DataFrame(columns=["code", "contract", "price", "change", "volume_tl", "volume_qty", "category"])

        return pd.concat(dfs, ignore_index=True)

    def get_options(self, category: str = "all") -> pd.DataFrame:
        """
        Get options contracts.

        Args:
            category: Filter by category:
                - "all": All options
                - "stock": Stock options (Pay Opsiyon)
                - "index": Index options (Endeks Opsiyon)

        Returns:
            DataFrame with columns: code, contract, price, change, volume_tl, volume_qty
        """
        soup = self._fetch_page()

        category_map = {
            "stock": ["stock_options"],
            "index": ["index_options"],
            "all": ["stock_options", "index_options"],
        }

        sections = category_map.get(category, category_map["all"])
        dfs = []

        for section_key in sections:
            section_name = self.SECTIONS.get(section_key)
            if section_name:
                df = self._parse_table(soup, section_name)
                if not df.empty:
                    df["category"] = section_key.replace("_options", "")
                    dfs.append(df)

        if not dfs:
            return pd.DataFrame(columns=["code", "contract", "price", "change", "volume_tl", "volume_qty", "category"])

        return pd.concat(dfs, ignore_index=True)

    def get_all(self) -> dict[str, pd.DataFrame]:
        """
        Get all VİOP data.

        Returns:
            Dictionary with 'futures' and 'options' DataFrames.
        """
        return {
            "futures": self.get_futures("all"),
            "options": self.get_options("all"),
        }

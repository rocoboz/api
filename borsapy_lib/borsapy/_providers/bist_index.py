"""BIST index constituent provider - downloads index components from BIST CSV."""

from io import StringIO
from typing import Any

import pandas as pd

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL

# BIST index components CSV URL
INDEX_COMPONENTS_URL = "https://www.borsaistanbul.com/datum/hisse_endeks_ds.csv"

# Singleton instance
_provider: "BistIndexProvider | None" = None


def get_bist_index_provider() -> "BistIndexProvider":
    """Get or create the singleton BistIndexProvider instance."""
    global _provider
    if _provider is None:
        _provider = BistIndexProvider()
    return _provider


class BistIndexProvider(BaseProvider):
    """Provider for BIST index constituents from official CSV file."""

    def __init__(self):
        super().__init__(timeout=30.0)
        self._df_cache: pd.DataFrame | None = None

    def _download_components(self) -> pd.DataFrame | None:
        """Download and cache the components CSV."""
        if self._df_cache is not None:
            return self._df_cache

        # Check memory cache first
        cache_key = "bist:index:components:all"
        cached = self._cache_get(cache_key)
        if cached is not None:
            self._df_cache = cached
            return cached

        try:
            response = self._get(INDEX_COMPONENTS_URL)
            df = pd.read_csv(StringIO(response.text), sep=";")
            # Skip header row (has English column names)
            df = df.iloc[1:]
            # Clean up symbol codes (remove .E suffix)
            df["symbol"] = df["BILESEN KODU"].str.replace(r"\.E$", "", regex=True)
            df["name"] = df["BULTEN_ADI"]
            df["index_code"] = df["ENDEKS KODU"]
            df["index_name"] = df["ENDEKS ADI"]

            self._df_cache = df
            self._cache_set(cache_key, df, TTL.COMPANY_LIST)
            return df
        except Exception:
            return None

    def get_components(self, symbol: str) -> list[dict[str, Any]]:
        """
        Get constituent stocks for an index.

        Args:
            symbol: Index symbol (e.g., "XU100", "XU030", "XKTUM").

        Returns:
            List of component dicts with 'symbol' and 'name' keys.
            Empty list if index not found or fetch fails.

        Examples:
            >>> provider = get_bist_index_provider()
            >>> provider.get_components("XU030")
            [{'symbol': 'AKBNK', 'name': 'AKBANK'}, ...]
        """
        symbol = symbol.upper()

        df = self._download_components()
        if df is None:
            return []

        # Filter by index code
        mask = df["index_code"] == symbol
        components = df[mask][["symbol", "name"]].to_dict("records")

        return components

    def get_available_indices(self) -> list[dict[str, Any]]:
        """
        Get list of all indices with component counts.

        Returns:
            List of dicts with 'symbol', 'name', and 'count' keys.
        """
        df = self._download_components()
        if df is None:
            return []

        # Group by index code
        grouped = df.groupby(["index_code", "index_name"]).size().reset_index(name="count")
        indices = [
            {"symbol": row["index_code"], "name": row["index_name"], "count": row["count"]}
            for _, row in grouped.iterrows()
        ]

        return sorted(indices, key=lambda x: x["symbol"])

    def is_in_index(self, ticker: str, index_symbol: str) -> bool:
        """
        Check if a stock is in a specific index.

        Args:
            ticker: Stock symbol (e.g., "THYAO").
            index_symbol: Index symbol (e.g., "XU030").

        Returns:
            True if stock is in the index.
        """
        ticker = ticker.upper()
        index_symbol = index_symbol.upper()

        df = self._download_components()
        if df is None:
            return False

        mask = (df["symbol"] == ticker) & (df["index_code"] == index_symbol)
        return mask.any()

    def get_indices_for_ticker(self, ticker: str) -> list[str]:
        """
        Get all indices that contain a specific stock.

        Args:
            ticker: Stock symbol (e.g., "THYAO").

        Returns:
            List of index symbols that contain this stock.
        """
        ticker = ticker.upper()

        df = self._download_components()
        if df is None:
            return []

        mask = df["symbol"] == ticker
        indices = df[mask]["index_code"].unique().tolist()

        return sorted(indices)

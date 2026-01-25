"""VİOP (Vadeli İşlem ve Opsiyon Piyasası) module for Turkish derivatives market."""

from functools import cached_property

import pandas as pd

from borsapy._providers.viop import get_viop_provider

__all__ = ["VIOP"]


class VIOP:
    """
    VİOP (Vadeli İşlem ve Opsiyon Piyasası) data access.

    Provides access to Turkish derivatives market data including
    futures and options contracts.

    Data source: İş Yatırım (HTML scraping)
    Note: Data is delayed by ~15 minutes

    Examples:
        >>> from borsapy import VIOP
        >>> viop = VIOP()
        >>> viop.futures  # All futures contracts
        >>> viop.stock_futures  # Stock futures only
        >>> viop.options  # All options contracts
    """

    def __init__(self) -> None:
        """Initialize VİOP data accessor."""
        self._provider = get_viop_provider()

    @cached_property
    def futures(self) -> pd.DataFrame:
        """
        Get all futures contracts.

        Returns:
            DataFrame with columns:
                - code: Contract code (e.g., F_AKBNK0226)
                - contract: Contract name (e.g., AKBNK Şubat 2026 Vadeli)
                - price: Last price
                - change: Price change
                - volume_tl: Trading volume in TL
                - volume_qty: Trading volume in contracts
                - category: stock, index, currency, or commodity
        """
        return self._provider.get_futures("all")

    @cached_property
    def stock_futures(self) -> pd.DataFrame:
        """
        Get stock futures contracts (Pay Vadeli İşlem).

        Returns:
            DataFrame with futures on individual stocks.
        """
        return self._provider.get_futures("stock")

    @cached_property
    def index_futures(self) -> pd.DataFrame:
        """
        Get index futures contracts (Endeks Vadeli İşlem).

        Includes XU030, XLBNK, etc.

        Returns:
            DataFrame with index futures.
        """
        return self._provider.get_futures("index")

    @cached_property
    def currency_futures(self) -> pd.DataFrame:
        """
        Get currency futures contracts (Döviz Vadeli İşlem).

        Includes USD/TRY, EUR/TRY, etc.

        Returns:
            DataFrame with currency futures.
        """
        return self._provider.get_futures("currency")

    @cached_property
    def commodity_futures(self) -> pd.DataFrame:
        """
        Get commodity futures contracts (Kıymetli Madenler).

        Includes gold, silver, platinum, palladium.

        Returns:
            DataFrame with commodity futures.
        """
        return self._provider.get_futures("commodity")

    @cached_property
    def options(self) -> pd.DataFrame:
        """
        Get all options contracts.

        Returns:
            DataFrame with columns:
                - code: Contract code
                - contract: Contract name
                - price: Last price
                - change: Price change
                - volume_tl: Trading volume in TL
                - volume_qty: Trading volume in contracts
                - category: stock or index
        """
        return self._provider.get_options("all")

    @cached_property
    def stock_options(self) -> pd.DataFrame:
        """
        Get stock options contracts (Pay Opsiyon).

        Returns:
            DataFrame with options on individual stocks.
        """
        return self._provider.get_options("stock")

    @cached_property
    def index_options(self) -> pd.DataFrame:
        """
        Get index options contracts (Endeks Opsiyon).

        Returns:
            DataFrame with index options.
        """
        return self._provider.get_options("index")

    def get_by_symbol(self, symbol: str) -> pd.DataFrame:
        """
        Get all derivatives for a specific underlying symbol.

        Args:
            symbol: Underlying symbol (e.g., "AKBNK", "THYAO", "XU030")

        Returns:
            DataFrame with all futures and options for the symbol.
        """
        symbol = symbol.upper()

        futures = self._provider.get_futures("all")
        options = self._provider.get_options("all")

        # Filter out empty DataFrames before concat
        dfs = [df for df in [futures, options] if not df.empty]
        if not dfs:
            return pd.DataFrame(columns=["code", "contract", "price", "change", "volume_tl", "volume_qty", "category"])

        all_data = pd.concat(dfs, ignore_index=True)

        # Filter by symbol in contract name or code
        mask = (
            all_data["contract"].str.upper().str.contains(symbol, na=False) |
            all_data["code"].str.upper().str.contains(symbol, na=False)
        )

        return all_data[mask].reset_index(drop=True)

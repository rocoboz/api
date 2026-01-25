"""Turkish sovereign Eurobond data.

Provides access to Turkish government bonds issued in foreign currencies
(USD and EUR denominated).

Examples:
    >>> import borsapy as bp

    # Get single Eurobond by ISIN
    >>> bond = bp.Eurobond("US900123DG28")
    >>> bond.isin                     # "US900123DG28"
    >>> bond.maturity                 # datetime(2033, 1, 19)
    >>> bond.currency                 # "USD"
    >>> bond.bid_yield                # 6.55
    >>> bond.ask_yield                # 6.24
    >>> bond.info                     # All data as dict

    # List all Eurobonds
    >>> bp.eurobonds()                # DataFrame with all Eurobonds
    >>> bp.eurobonds(currency="USD")  # Only USD bonds
    >>> bp.eurobonds(currency="EUR")  # Only EUR bonds
"""

from datetime import datetime

import pandas as pd

from borsapy._providers.ziraat_eurobond import get_eurobond_provider
from borsapy.exceptions import DataNotAvailableError


class Eurobond:
    """Single Turkish sovereign Eurobond interface.

    Provides access to bond data including prices, yields,
    maturity, and other characteristics.

    Attributes:
        isin: ISIN code of the bond.
        maturity: Maturity date.
        days_to_maturity: Days until maturity.
        currency: Bond currency (USD or EUR).
        bid_price: Bid price (buying price).
        bid_yield: Bid yield (buying yield).
        ask_price: Ask price (selling price).
        ask_yield: Ask yield (selling yield).
        info: All bond data as dictionary.

    Examples:
        >>> bond = Eurobond("US900123DG28")
        >>> bond.bid_yield
        6.55
        >>> bond.currency
        'USD'
    """

    def __init__(self, isin: str):
        """Initialize Eurobond by ISIN.

        Args:
            isin: ISIN code (e.g., "US900123DG28").

        Raises:
            DataNotAvailableError: If bond not found.
        """
        self._isin = isin.upper()
        self._provider = get_eurobond_provider()
        self._data_cache: dict | None = None

    @property
    def _data(self) -> dict:
        """Lazy-loaded bond data."""
        if self._data_cache is None:
            self._data_cache = self._provider.get_eurobond(self._isin)
            if self._data_cache is None:
                raise DataNotAvailableError(f"Eurobond not found: {self._isin}")
        return self._data_cache

    @property
    def isin(self) -> str:
        """ISIN code of the bond."""
        return self._data["isin"]

    @property
    def maturity(self) -> datetime | None:
        """Maturity date of the bond."""
        return self._data.get("maturity")

    @property
    def days_to_maturity(self) -> int:
        """Number of days until maturity."""
        return self._data.get("days_to_maturity", 0)

    @property
    def currency(self) -> str:
        """Bond currency (USD or EUR)."""
        return self._data.get("currency", "")

    @property
    def bid_price(self) -> float | None:
        """Bid price (buying price)."""
        return self._data.get("bid_price")

    @property
    def bid_yield(self) -> float | None:
        """Bid yield (buying yield) as percentage."""
        return self._data.get("bid_yield")

    @property
    def ask_price(self) -> float | None:
        """Ask price (selling price)."""
        return self._data.get("ask_price")

    @property
    def ask_yield(self) -> float | None:
        """Ask yield (selling yield) as percentage."""
        return self._data.get("ask_yield")

    @property
    def info(self) -> dict:
        """All bond data as dictionary.

        Returns:
            Dict with all bond attributes.
        """
        return self._data.copy()

    def __repr__(self) -> str:
        """String representation."""
        try:
            maturity_year = self.maturity.year if self.maturity else "?"
            return f"Eurobond({self._isin}, {self.currency}, {maturity_year}, yield={self.bid_yield}%)"
        except DataNotAvailableError:
            return f"Eurobond({self._isin})"


def eurobonds(currency: str | None = None) -> pd.DataFrame:
    """Get all Turkish sovereign Eurobonds as DataFrame.

    Args:
        currency: Optional filter by currency ("USD" or "EUR").

    Returns:
        DataFrame with columns: isin, maturity, days_to_maturity,
        currency, bid_price, bid_yield, ask_price, ask_yield.

    Examples:
        >>> import borsapy as bp
        >>> bp.eurobonds()                # All Eurobonds
        >>> bp.eurobonds(currency="USD")  # USD bonds only
        >>> bp.eurobonds(currency="EUR")  # EUR bonds only
    """
    provider = get_eurobond_provider()
    data = provider.get_eurobonds(currency=currency)

    if not data:
        return pd.DataFrame(
            columns=[
                "isin",
                "maturity",
                "days_to_maturity",
                "currency",
                "bid_price",
                "bid_yield",
                "ask_price",
                "ask_yield",
            ]
        )

    df = pd.DataFrame(data)
    df = df.sort_values("maturity")
    return df

"""TCMB (Turkish Central Bank) interest rates.

Provides access to TCMB policy rates:
- 1-week repo rate (policy rate)
- Overnight (O/N) corridor rates
- Late liquidity window (LON) rates

Examples:
    >>> import borsapy as bp

    # Get TCMB rates
    >>> tcmb = bp.TCMB()
    >>> tcmb.policy_rate              # 38.0
    >>> tcmb.overnight                # {'borrowing': 36.5, 'lending': 41.0}
    >>> tcmb.late_liquidity           # {'borrowing': 0.0, 'lending': 44.0}
    >>> tcmb.rates                    # DataFrame with all rates

    # Historical data
    >>> tcmb.history("policy")        # Policy rate history (2010+)
    >>> tcmb.history("overnight")     # Overnight rate history (2002+)

    # Shortcut function
    >>> bp.policy_rate()              # 38.0
"""

from datetime import datetime, timedelta

import pandas as pd

from borsapy._providers.tcmb_rates import get_tcmb_rates_provider


class TCMB:
    """TCMB interest rates interface.

    Provides access to Turkish Central Bank policy rates including
    the 1-week repo rate (main policy rate), overnight corridor,
    and late liquidity window rates.

    Attributes:
        policy_rate: Current 1-week repo rate (policy rate).
        overnight: Overnight corridor rates (borrowing/lending).
        late_liquidity: Late liquidity window rates (borrowing/lending).
        rates: DataFrame with all current rates.

    Examples:
        >>> tcmb = TCMB()
        >>> tcmb.policy_rate
        38.0
        >>> tcmb.overnight
        {'borrowing': 36.5, 'lending': 41.0}
    """

    def __init__(self):
        """Initialize TCMB interface."""
        self._provider = get_tcmb_rates_provider()

    @property
    def policy_rate(self) -> float | None:
        """Get current 1-week repo rate (policy rate).

        This is the main policy interest rate set by TCMB.

        Returns:
            Policy rate as percentage (e.g., 38.0 for 38%).
        """
        data = self._provider.get_policy_rate()
        return data.get("lending")

    @property
    def overnight(self) -> dict:
        """Get overnight (O/N) corridor rates.

        The overnight corridor defines the band within which
        short-term interest rates can fluctuate.

        Returns:
            Dict with 'borrowing' and 'lending' rates.

        Example:
            {'borrowing': 36.5, 'lending': 41.0}
        """
        data = self._provider.get_overnight_rates()
        return {
            "borrowing": data.get("borrowing"),
            "lending": data.get("lending"),
        }

    @property
    def late_liquidity(self) -> dict:
        """Get late liquidity window (LON) rates.

        The late liquidity window is a facility for banks
        to borrow/lend at the end of the day.

        Returns:
            Dict with 'borrowing' and 'lending' rates.

        Example:
            {'borrowing': 0.0, 'lending': 44.0}
        """
        data = self._provider.get_late_liquidity_rates()
        return {
            "borrowing": data.get("borrowing"),
            "lending": data.get("lending"),
        }

    @property
    def rates(self) -> pd.DataFrame:
        """Get all current rates as DataFrame.

        Returns:
            DataFrame with columns: type, borrowing, lending.

        Example:
            >>> tcmb.rates
                       type  borrowing  lending
            0        policy       None     38.0
            1     overnight       36.5     41.0
            2  late_liquidity      0.0     44.0
        """
        data = self._provider.get_all_rates()
        df = pd.DataFrame(data)
        if "rate_type" in df.columns:
            df = df.rename(columns={"rate_type": "type"})
        return df[["type", "borrowing", "lending"]]

    def history(
        self,
        rate_type: str = "policy",
        period: str | None = None,
    ) -> pd.DataFrame:
        """Get historical rates for given type.

        Args:
            rate_type: One of "policy", "overnight", "late_liquidity".
            period: Optional period filter (e.g., "1y", "5y", "max").
                   If None, returns all available data.

        Returns:
            DataFrame with date index and borrowing/lending columns.

        Example:
            >>> tcmb.history("policy", period="1y")
                        borrowing  lending
            date
            2024-01-25       None     45.0
            2024-02-22       None     45.0
            ...
        """
        data = self._provider.get_rate_history(rate_type)

        if not data:
            return pd.DataFrame(columns=["date", "borrowing", "lending"])

        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        # Apply period filter if specified
        if period:
            end_date = datetime.now()
            period_map = {
                "1w": timedelta(days=7),
                "1mo": timedelta(days=30),
                "3mo": timedelta(days=90),
                "6mo": timedelta(days=180),
                "1y": timedelta(days=365),
                "2y": timedelta(days=730),
                "5y": timedelta(days=1825),
                "10y": timedelta(days=3650),
            }

            if period.lower() in period_map:
                start_date = end_date - period_map[period.lower()]
                df = df[df.index >= start_date]
            # "max" or unknown period returns all data

        return df

    def __repr__(self) -> str:
        """String representation."""
        rate = self.policy_rate
        if rate is not None:
            return f"TCMB(policy_rate={rate}%)"
        return "TCMB()"


def policy_rate() -> float | None:
    """Get current TCMB policy rate (1-week repo).

    This is a shortcut function for quick access to the
    main policy interest rate.

    Returns:
        Policy rate as percentage (e.g., 38.0 for 38%).

    Example:
        >>> import borsapy as bp
        >>> bp.policy_rate()
        38.0
    """
    return TCMB().policy_rate

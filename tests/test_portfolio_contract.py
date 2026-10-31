"""Offline contract tests for portfolio analysis and bond parsing.

Run with the project virtual environment:

    .venv/Scripts/python.exe tests/test_portfolio_contract.py
"""

from __future__ import annotations

import os
import sys
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from api_core.app import create_app
from finans_core._providers.dovizcom_tahvil import DovizcomTahvilProvider
from finans_core.portfolio import Portfolio
from fastapi.testclient import TestClient


class FakeAsset:
    """Price source that serves a prepared frame instead of the network."""

    def __init__(self, frame: pd.DataFrame):
        self._frame = frame

    def history(self, period: str = "1y", **kwargs) -> pd.DataFrame:
        return self._frame.copy()


def _frame(dates, closes, tz: str | None = None) -> pd.DataFrame:
    index = pd.DatetimeIndex(dates)
    if tz is not None:
        index = index.tz_localize(tz)
    return pd.DataFrame({"Close": closes}, index=index)


def _portfolio(assets, shares, purchase_dates=None) -> Portfolio:
    portfolio = Portfolio()
    purchase_dates = purchase_dates or {}
    for symbol, frame in assets.items():
        portfolio.add(
            symbol,
            shares=shares[symbol],
            cost=1.0,
            asset_type="fx",
            purchase_date=purchase_dates.get(symbol),
        )
        portfolio._asset_cache[f"{symbol}_fx"] = FakeAsset(frame)
    return portfolio


def _oscillating_portfolio(tz: str | None = None):
    dates = pd.bdate_range("2023-01-02", periods=260)
    daily_asset_returns = np.array(
        [0.01 if i % 2 == 0 else -0.01 for i in range(len(dates))]
    )
    prices = 100 * np.cumprod(1 + daily_asset_returns)
    portfolio = _portfolio(
        {"AAA": _frame(dates, prices, tz=tz)}, {"AAA": 1}
    )
    return portfolio, dates, daily_asset_returns


def test_history_starts_when_all_assets_are_covered():
    dates_a = pd.bdate_range("2024-01-01", periods=6)
    dates_b = pd.bdate_range("2024-01-03", periods=4)
    portfolio = _portfolio(
        {"AAA": _frame(dates_a, [100.0] * 6), "BBB": _frame(dates_b, [200.0] * 4)},
        {"AAA": 2, "BBB": 1},
    )

    history = portfolio.history("3mo")

    assert list(history.columns) == ["Value", "Daily_Return"]
    # Before 2024-01-03 only AAA has a quote; a partial sum would be 200.
    assert history.index[0] == pd.Timestamp("2024-01-03")
    assert (history["Value"] == 400.0).all()
    assert history["Value"].notna().all()
    assert np.isnan(history["Daily_Return"].iloc[0])
    assert (history["Daily_Return"].iloc[1:] == 0).all()


def test_history_forward_fills_inner_missing_dates():
    dates_a = pd.bdate_range("2024-01-01", periods=5)
    dates_b = pd.DatetimeIndex(
        [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02"),
         pd.Timestamp("2024-01-03"), pd.Timestamp("2024-01-05")]
    )
    portfolio = _portfolio(
        {"AAA": _frame(dates_a, [100.0] * 5), "BBB": _frame(dates_b, [200.0] * 4)},
        {"AAA": 2, "BBB": 1},
    )

    history = portfolio.history("3mo")

    assert len(history) == 5
    assert (history["Value"] == 400.0).all()
    assert np.isnan(history["Daily_Return"].iloc[0])
    assert (history["Daily_Return"].iloc[1:] == 0).all()


def test_purchase_date_none_uses_full_history():
    dates = pd.bdate_range("2024-01-01", periods=5)
    portfolio = _portfolio({"AAA": _frame(dates, [10.0] * 5)}, {"AAA": 1})

    history = portfolio.history("3mo")

    assert history.index[0] == dates[0]


def test_purchase_date_filters_history():
    dates = pd.bdate_range("2024-01-01", periods=10)
    portfolio = _portfolio(
        {"AAA": _frame(dates, [10.0] * 10)},
        {"AAA": 1},
        purchase_dates={"AAA": date(2024, 1, 8)},
    )

    history = portfolio.history("3mo")

    assert history.index[0] == pd.Timestamp("2024-01-08")
    assert history.index[-1] == dates[-1]


def test_risk_metrics_use_calendar_span_annualization():
    portfolio, dates, _ = _oscillating_portfolio()
    history = portfolio.history("1y")
    returns = history["Daily_Return"].dropna()
    years = (dates[-1] - dates[0]).days / 365.25
    periods_per_year = len(returns) / years

    total_return = history["Value"].iloc[-1] / history["Value"].iloc[0] - 1
    expected_return = ((1 + total_return) ** (1 / years) - 1) * 100
    expected_volatility = returns.std() * np.sqrt(periods_per_year) * 100
    expected_drawdown = (
        history["Value"] / history["Value"].cummax() - 1
    ).min() * 100

    metrics = portfolio.risk_metrics("1y", risk_free_rate=0.30)

    assert metrics["risk_free_rate"] == 30.0
    assert metrics["risk_free_rate_source"] == "request"
    assert metrics["trading_days"] == len(returns)
    assert abs(metrics["annualized_return"] - expected_return) <= 0.01
    assert abs(metrics["annualized_volatility"] - expected_volatility) <= 0.01
    assert abs(metrics["max_drawdown"] - expected_drawdown) <= 0.01
    # A fixed sqrt(252) assumption would put volatility off by ~0.3 points.
    assert abs(metrics["annualized_volatility"] - returns.std() * np.sqrt(252) * 100) > 0.1
    expected_sharpe = (expected_return - 30.0) / expected_volatility
    assert abs(metrics["sharpe_ratio"] - expected_sharpe) <= 0.01


def test_beta_aligns_timezone_aware_benchmark():
    dates = pd.bdate_range("2023-01-02", periods=260)
    benchmark_returns = np.array(
        [0.01 if i % 2 == 0 else -0.01 for i in range(len(dates))]
    )
    portfolio_prices = 100 * np.cumprod(1 + 2 * benchmark_returns)
    benchmark_prices = 100 * np.cumprod(1 + benchmark_returns)
    portfolio = _portfolio(
        {"AAA": _frame(dates, portfolio_prices, tz="Europe/Istanbul")},
        {"AAA": 1},
    )
    benchmark_frame = _frame(dates, benchmark_prices, tz="Europe/Istanbul")

    class FakeIndex:
        def __init__(self, symbol: str):
            self.symbol = symbol

        def history(self, period: str = "1y", **kwargs) -> pd.DataFrame:
            return benchmark_frame.copy()

    with patch("finans_core.portfolio.Index", FakeIndex):
        metrics = portfolio.risk_metrics("1y", risk_free_rate=0.0)

    assert metrics["benchmark"] == "XU100"
    assert metrics["beta"] is not None
    assert abs(metrics["beta"] - 2.0) <= 0.01
    assert metrics["alpha"] is not None


def test_missing_risk_free_rate_stays_missing():
    portfolio, _, _ = _oscillating_portfolio()

    with patch("finans_core.bond.risk_free_rate", return_value=None):
        metrics = portfolio.risk_metrics("1y")

    assert metrics["risk_free_rate"] is None
    assert metrics["risk_free_rate_source"] == "unavailable"
    assert metrics["sharpe_ratio"] is None
    assert metrics["sortino_ratio"] is None
    assert metrics["alpha"] is None


def test_short_history_returns_empty_metrics():
    dates = pd.bdate_range("2024-01-01", periods=10)
    portfolio = _portfolio({"AAA": _frame(dates, [10.0] * 10)}, {"AAA": 1})

    metrics = portfolio.risk_metrics("1mo")

    assert metrics["trading_days"] == 0
    assert metrics["annualized_return"] is None
    assert metrics["max_drawdown"] is None
    assert metrics["risk_free_rate_source"] == "unavailable"

    empty = Portfolio().risk_metrics("1mo")
    assert empty["trading_days"] == 0


class FakeTahvilProvider(DovizcomTahvilProvider):
    def __init__(self, html: str):
        self.html = html

    def _get(self, url, **kwargs) -> SimpleNamespace:
        return SimpleNamespace(content=self.html.encode("utf-8"))

    def _cache_get(self, key: str):
        return None

    def _cache_set(self, key: str, value, ttl: int) -> None:
        return None


def _bond_html(table_id: str = "bonds") -> str:
    return f"""
    <html><body>
      <table id="{table_id}"><tbody>
        <tr>
          <td><a href="/tahvil/2-yillik">2 Yıllık Tahvil</a></td>
          <td>39,67</td><td>1,25</td>
        </tr>
        <tr>
          <td><a href="/tahvil/10-yillik">10 Yıllık Tahvil</a></td>
          <td>35,71</td><td>-0,40</td>
        </tr>
      </tbody></table>
    </body></html>
    """


def test_bond_parser_accepts_current_markup():
    provider = FakeTahvilProvider(_bond_html())

    bonds = provider.get_bond_yields()
    ten_year = provider.get_bond("10Y")

    assert len(bonds) == 2
    assert ten_year["name"] == "10 Yıllık Tahvil"
    assert ten_year["maturity"] == "10Y"
    assert ten_year["yield"] == 35.71
    assert abs(ten_year["yield_decimal"] - 0.3571) < 1e-9
    assert abs(ten_year["change"] - (35.71 * -0.004)) < 1e-9
    assert abs(provider.get_10y_yield() - 0.3571) < 1e-9


def test_bond_parser_keeps_legacy_table_id():
    provider = FakeTahvilProvider(_bond_html("commodities"))

    assert len(provider.get_bond_yields()) == 2


def test_analysis_rejects_invalid_payload():
    client = TestClient(create_app())

    invalid_type = client.post(
        "/portfolio/analysis",
        json={"holdings": [{"symbol": "THYAO", "shares": 1, "asset_type": "bogus"}]},
    )
    invalid_date = client.post(
        "/portfolio/analysis",
        json={
            "holdings": [
                {"symbol": "THYAO", "shares": 1, "purchase_date": "2024-13-40"}
            ]
        },
    )

    assert invalid_type.status_code == 422
    assert invalid_date.status_code == 422


def test_analysis_failure_maps_to_500():
    class ExplodingPortfolio:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("boom")

    client = TestClient(create_app())

    with patch("api_core.routes.portfolio.Portfolio", ExplodingPortfolio):
        response = client.post(
            "/portfolio/analysis",
            json={"holdings": [{"symbol": "THYAO", "shares": 1, "cost": 1.0}]},
        )

    assert response.status_code == 500
    assert "Portfolio analysis failed" in response.json()["detail"]


def main() -> int:
    tests = [
        test_history_starts_when_all_assets_are_covered,
        test_history_forward_fills_inner_missing_dates,
        test_purchase_date_none_uses_full_history,
        test_purchase_date_filters_history,
        test_risk_metrics_use_calendar_span_annualization,
        test_beta_aligns_timezone_aware_benchmark,
        test_missing_risk_free_rate_stays_missing,
        test_short_history_returns_empty_metrics,
        test_bond_parser_accepts_current_markup,
        test_bond_parser_keeps_legacy_table_id,
        test_analysis_rejects_invalid_payload,
        test_analysis_failure_maps_to_500,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)} test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline contract tests for the FX layer.

Run with the project virtual environment:

    .venv/Scripts/python.exe tests/test_fx_contract.py
"""

from __future__ import annotations

import os
import sys

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from api_core.routes import fx as fx_routes
from api_core.services.normalizers import df_to_json
from finans_core.assets import get_asset_spec, resolve_asset_code


def test_canlidoviz_ids():
    expected = {
        "gram-altin": 32,
        "has-altin": 1179,
        "ceyrek-altin": 11,
        "yarim-altin": 47,
        "tam-altin": 14,
        "cumhuriyet-altin": 27,
        "ata-altin": 58,
        "resat-altin": 43,
        "gremse-altin": 15,
        "22-ayar-bilezik": 18,
        "18-ayar-altin": 55,
        "14-ayar-altin": 16,
        "ons-altin": 12,
        "gram-gumus": 20,
        "gram-platin": 1012,
    }
    for code, item_id in expected.items():
        spec = get_asset_spec(code)
        assert spec is not None, code
        assert spec.canlidoviz_id == item_id, (code, spec.canlidoviz_id, item_id)


def test_ons_quote_currency():
    spec = get_asset_spec("ons-altin")
    assert spec is not None
    assert spec.quote_currency == "USD"
    assert get_asset_spec("gram-altin").quote_currency == "TRY"


def test_alias_resolution():
    cases = {
        "ons-altin-usd": "ons-altin",
        "XAU": "ons-altin",
        "xauusd": "ons-altin",
        "gram": "gram-altin",
        "ALTIN": "gram-altin",
        "resat": "resat-altin",
        "resat-lira-altin": "resat-altin",
        "bilezik": "22-ayar-bilezik",
        "gumus": "gram-gumus",
        "xag-usd": "XAG-USD",
        "brent": "BRENT",
        "usd": "USD",
    }
    for raw, expected in cases.items():
        assert resolve_asset_code(raw) == expected, (raw, resolve_asset_code(raw), expected)


def test_history_keeps_dates():
    index = pd.DatetimeIndex(
        [pd.Timestamp("2026-10-29", tz="UTC"), pd.Timestamp("2026-10-30", tz="UTC")],
        name="date",
    )
    frame = pd.DataFrame({"Open": [1.0, 2.0], "Close": [1.5, 2.5]}, index=index)
    rows = df_to_json(frame)
    assert len(rows) == 2
    assert "date" in rows[0], rows[0]
    assert rows[0]["date"].startswith("2026-10-29")
    assert rows[0]["Close"] == 1.5


def test_formula_fallback():
    # 10 gram has gold priced at 6.000 TL, 0.995 purity.
    assert fx_routes._formula_price("22-ayar-bilezik", 6000) == round(
        6000 * (0.9166 / 0.995), 2
    )
    assert fx_routes._formula_price("ceyrek-altin", 6000) == round(
        6000 * (1.6065 / 0.995) * 1.03, 2
    )
    assert fx_routes._formula_price("gram-altin", 0) is None


def test_gold_matrix_uses_live_quotes():
    quotes = {
        "gram-altin": {"last": 6000.0, "open": 5900.0, "high": 6100.0, "low": 5850.0,
                       "currency": "TRY", "source": "canlidoviz", "price_type": "daily_close",
                       "updated_at": "2026-10-30T00:00:00+00:00"},
        "USD": {"last": 50.0, "currency": "TRY", "source": "canlidoviz",
                "price_type": "daily_close", "updated_at": "2026-10-30T00:00:00+00:00"},
        "ons-altin": {"last": 190000.0, "open": 188000.0, "high": 191000.0, "low": 187500.0,
                      "currency": "TRY", "source": "canlidoviz", "price_type": "daily_close",
                      "source_currency": "USD", "source_price": 3800.0,
                      "conversion_rate": 50.0, "conversion_pair": "USDTRY",
                      "updated_at": "2026-10-30T00:00:00+00:00"},
        "ceyrek-altin": {"last": 10000.0, "currency": "TRY", "source": "canlidoviz",
                         "price_type": "daily_close", "updated_at": "2026-10-30T00:00:00+00:00"},
    }

    original_fetch = fx_routes._fetch_quotes
    fx_routes._fetch_quotes = lambda codes, in_try=True: {
        code: info for code, info in quotes.items() if code in codes
    }
    try:
        payload = fx_routes._get_all_gold_types_payload()
    finally:
        fx_routes._fetch_quotes = original_fetch

    rates = payload["base_rates"]
    assert rates["gram_altin_try"] == 6000.0
    assert rates["usd_try"] == 50.0
    assert rates["ons_altin_usd"] == 3800.0
    assert rates["ons_altin_try"] == 190000.0

    items = {item["code"]: item for item in payload["gold_types"]}

    assert items["gram-altin"]["source"] == "canlidoviz"
    assert items["gram-altin"]["price"] == 6000.0

    # Ounce is reported in TRY by the matrix and keeps the USD source quote.
    assert items["ons-altin"]["currency"] == "TRY"
    assert items["ons-altin"]["price"] == 190000.0
    assert items["ons-altin"]["source_price"] == 3800.0
    assert items["ons-altin-usd"]["currency"] == "USD"
    assert items["ons-altin-usd"]["price"] == 3800.0

    # A missing quote falls back to the formula and is labelled as such.
    assert items["ata-altin"]["source"] == "formula"
    assert items["ata-altin"]["derived_from"] == "gram-altin"
    assert items["ata-altin"]["price"] == round(6000 * (6.609 / 0.995) * 1.035, 2)


def test_quote_normalization():
    assert fx_routes._normalize_quote(None) == "TRY"
    assert fx_routes._normalize_quote("source") == "SOURCE"
    try:
        fx_routes._normalize_quote("EUR")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("invalid quote value was accepted")


def main() -> int:
    tests = [
        test_canlidoviz_ids,
        test_ons_quote_currency,
        test_alias_resolution,
        test_history_keeps_dates,
        test_formula_fallback,
        test_gold_matrix_uses_live_quotes,
        test_quote_normalization,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)} test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

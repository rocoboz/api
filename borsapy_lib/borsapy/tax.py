"""Withholding tax (stopaj) rates for Turkish investment funds.

Static reference table based on Gelir Vergisi Kanunu gecici 67. madde.
Tax rates depend on fund category, purchase date, and optionally holding duration.

Source: Ziraat Bank withholding tax table + TEFAS category mapping.
"""

from datetime import date

import pandas as pd

# ---------------------------------------------------------------------------
# Tax category identifiers
# ---------------------------------------------------------------------------

TAX_CAT_VARIABLE = "degisken_karma_doviz"
TAX_CAT_EQUITY_HEAVY = "pay_senedi_yogun"
TAX_CAT_OTHER = "borclanma_para_maden"
TAX_CAT_GSYF_GYF_LONG = "gsyf_gyf_uzun"
TAX_CAT_GSYF_GYF_SHORT = "gsyf_gyf_kisa"

# ---------------------------------------------------------------------------
# Date periods (start_inclusive, end_inclusive) — None means open-ended
# ---------------------------------------------------------------------------

TAX_PERIODS: list[tuple[date | None, date | None]] = [
    (None, date(2020, 12, 22)),
    (date(2020, 12, 23), date(2024, 4, 30)),
    (date(2024, 5, 1), date(2024, 10, 31)),
    (date(2024, 11, 1), date(2025, 1, 31)),
    (date(2025, 2, 1), date(2025, 7, 8)),
    (date(2025, 7, 9), None),
]

# ---------------------------------------------------------------------------
# Rate table: tax_category -> list of rates (one per period, as percentages)
# ---------------------------------------------------------------------------

TAX_RATES: dict[str, list[float]] = {
    TAX_CAT_VARIABLE:       [10.0, 10.0, 10.0, 10.0, 15.0, 17.5],
    TAX_CAT_EQUITY_HEAVY:   [0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
    TAX_CAT_OTHER:          [10.0, 0.0,  7.5,  10.0, 15.0, 17.5],
    TAX_CAT_GSYF_GYF_LONG: [0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
    TAX_CAT_GSYF_GYF_SHORT: [10.0, 0.0, 7.5,  10.0, 15.0, 17.5],
}

# ---------------------------------------------------------------------------
# Human-readable descriptions for each tax category
# ---------------------------------------------------------------------------

TAX_CAT_DESCRIPTIONS: dict[str, str] = {
    TAX_CAT_VARIABLE: "Degisken, karma, eurobond, dis borclanma, yabanci, serbest + doviz",
    TAX_CAT_EQUITY_HEAVY: "Pay senedi yogun fon",
    TAX_CAT_OTHER: "Borclanma araclari, para piyasasi, kiymetli maden, katilim",
    TAX_CAT_GSYF_GYF_LONG: "GSYF/GYF (>2 yil)",
    TAX_CAT_GSYF_GYF_SHORT: "GSYF/GYF (<2 yil)",
}

# ---------------------------------------------------------------------------
# TEFAS category -> tax category mapping
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# TEFAS category -> tax category mapping
#
# TEFAS returns two category fields:
#   FONKATEGORI (Fund.info "category"): "Hisse Senedi Fonu", "Değişken Fon", etc.
#   FONTURACIKLAMA (management_fees "fund_category"): "Hisse Senedi Şemsiye Fonu", etc.
#
# "Hisse Senedi Fonu" is ambiguous — it covers both domestic equity-heavy (0%)
# and foreign equity (variable rate). Name-based disambiguation is needed.
# ---------------------------------------------------------------------------

# Categories that map directly (no name check needed)
TEFAS_CATEGORY_MAP: dict[str, str] = {
    # --- TAX_CAT_VARIABLE ---
    # FONKATEGORI values
    "Değişken Fon": TAX_CAT_VARIABLE,
    "Karma Fon": TAX_CAT_VARIABLE,
    "Serbest Fon": TAX_CAT_VARIABLE,
    "Fon Sepeti Fonu": TAX_CAT_VARIABLE,
    "Yabancı Fon Sepeti Fonu": TAX_CAT_VARIABLE,
    # FONTURACIKLAMA (Şemsiye) values
    "Değişken Şemsiye Fonu": TAX_CAT_VARIABLE,
    "Karma Şemsiye Fonu": TAX_CAT_VARIABLE,
    "Serbest Şemsiye Fonu": TAX_CAT_VARIABLE,
    "Fon Sepeti Şemsiye Fonu": TAX_CAT_VARIABLE,
    # EMK-specific FONTURACIKLAMA values (not already covered above)
    "Dış Borçlanma Araçları Fonu": TAX_CAT_VARIABLE,
    "Katılım Değişken Fon": TAX_CAT_VARIABLE,
    "Yaşam Döngüsü/Hedef Fon": TAX_CAT_VARIABLE,
    # Short-form legacy values
    "Değişken": TAX_CAT_VARIABLE,
    "Karma": TAX_CAT_VARIABLE,
    "Serbest": TAX_CAT_VARIABLE,
    "Eurobond": TAX_CAT_VARIABLE,
    "Yabancı Hisse Senedi": TAX_CAT_VARIABLE,
    "Yabancı Borçlanma Araçları": TAX_CAT_VARIABLE,
    "Dış Borçlanma Araçları": TAX_CAT_VARIABLE,
    "Fon Sepeti": TAX_CAT_VARIABLE,
    # --- TAX_CAT_OTHER ---
    # FONKATEGORI values
    "Borçlanma Araçları Fonu": TAX_CAT_OTHER,
    "Para Piyasası Fonu": TAX_CAT_OTHER,
    "Kıymetli Madenler Fonu": TAX_CAT_OTHER,
    "Katılım Fonu": TAX_CAT_OTHER,
    # FONTURACIKLAMA (Şemsiye) values
    "Borçlanma Araçları Şemsiye Fonu": TAX_CAT_OTHER,
    "Para Piyasası Şemsiye Fonu": TAX_CAT_OTHER,
    "Kıymetli Madenler Şemsiye Fonu": TAX_CAT_OTHER,
    "Katılım Şemsiye Fonu": TAX_CAT_OTHER,
    # EMK-specific FONTURACIKLAMA values (not already covered above)
    "Kamu Borçlanma Araçları Fonu": TAX_CAT_OTHER,
    "Kamu Yabancı Para (Döviz) Cinsinden Borçlanma Araç": TAX_CAT_OTHER,
    "Özel Sektör Borçlanma Araçları Fonu": TAX_CAT_OTHER,
    "Endeks Fon": TAX_CAT_OTHER,
    "Standart Fon": TAX_CAT_OTHER,
    "OKS Standart Fon": TAX_CAT_OTHER,
    "OKS Katılım Standart Fon": TAX_CAT_OTHER,
    "Katılım Standart Fon": TAX_CAT_OTHER,
    "Kira Sertifikası Fonu": TAX_CAT_OTHER,
    "Kira Sertifikasi Katılım Fonu": TAX_CAT_OTHER,
    "Altın Fonu": TAX_CAT_OTHER,
    "Altın Katılım Fonu": TAX_CAT_OTHER,
    "Merkezi Alacağın Devri Fonu": TAX_CAT_OTHER,
    "Kıymetli Madenler": TAX_CAT_OTHER,
    "Katılım Katkı Fonu": TAX_CAT_OTHER,
    # FONKATEGORI alternate casing (EMK uses "Oks" instead of "OKS")
    "Oks Standart Fon": TAX_CAT_OTHER,
    "Oks Katılım Standart Fon": TAX_CAT_OTHER,
    # Short-form legacy values
    "Kısa Vadeli Borçlanma Araçları": TAX_CAT_OTHER,
    "Kısa Vadeli Borçlanma": TAX_CAT_OTHER,
    "Uzun Vadeli Borçlanma Araçları": TAX_CAT_OTHER,
    "Borçlanma Araçları": TAX_CAT_OTHER,
    "Para Piyasası": TAX_CAT_OTHER,
    "Kıymetli Maden": TAX_CAT_OTHER,
    "Katılım": TAX_CAT_OTHER,
    # --- TAX_CAT_GSYF_GYF (conservative default: short-term rate) ---
    "Girişim Sermayesi Yatırım Fonları": TAX_CAT_GSYF_GYF_SHORT,
    "Gayrimenkul Yatırım Fonları": TAX_CAT_GSYF_GYF_SHORT,
    "Girişim Sermayesi": TAX_CAT_GSYF_GYF_SHORT,
    "Gayrimenkul": TAX_CAT_GSYF_GYF_SHORT,
}

# Categories that need name-based disambiguation
_HISSE_CATEGORIES = {
    "Hisse Senedi Fonu",
    "Hisse Senedi Şemsiye Fonu",
    "Hisse Senedi",
    "Hisse Senedi Yoğun",
}

# Name keywords that indicate foreign equity → TAX_CAT_VARIABLE
_FOREIGN_EQUITY_KEYWORDS = ["yabancı", "yabanci"]


def _find_period_index(purchase_date: date) -> int:
    """Find the period index for a given purchase date."""
    for i, (start, end) in enumerate(TAX_PERIODS):
        if start is not None and purchase_date < start:
            continue
        if end is not None and purchase_date > end:
            continue
        return i
    # Should not reach here, but default to last period
    return len(TAX_PERIODS) - 1


def classify_fund_tax_category(category: str, fund_name: str = "") -> str | None:
    """Classify a fund into a tax category based on its TEFAS category.

    Args:
        category: TEFAS fund category string (e.g., "Değişken Fon",
                  "Hisse Senedi Fonu", "Borçlanma Araçları Şemsiye Fonu").
        fund_name: Fund full name, used for disambiguation of equity funds
                  and "döviz" keyword detection.

    Returns:
        Tax category identifier string, or None if unrecognized.
    """
    if not category:
        return None

    cat = category.strip()
    name_lower = fund_name.lower() if fund_name else ""

    # Hisse Senedi category needs name-based disambiguation
    if cat in _HISSE_CATEGORIES:
        # Foreign equity keywords → variable rate
        if any(kw in name_lower for kw in _FOREIGN_EQUITY_KEYWORDS):
            return TAX_CAT_VARIABLE
        # Default: domestic equity-heavy → 0%
        return TAX_CAT_EQUITY_HEAVY

    # Direct mapping
    if cat in TEFAS_CATEGORY_MAP:
        return TEFAS_CATEGORY_MAP[cat]

    # Fallback: "döviz" in fund name → variable
    if "döviz" in name_lower:
        return TAX_CAT_VARIABLE

    return None


def get_withholding_tax_rate(
    tax_category: str,
    purchase_date: date | str,
    holding_days: int | None = None,
) -> float:
    """Get the withholding tax rate for a given tax category and purchase date.

    Args:
        tax_category: Tax category identifier (e.g., TAX_CAT_VARIABLE).
        purchase_date: Date of fund purchase (date object or "YYYY-MM-DD" string).
        holding_days: Number of days the fund was held. Used for GSYF/GYF
                     categories where >730 days (2 years) qualifies for 0% rate.

    Returns:
        Tax rate as a decimal (e.g., 0.10 for 10%, 0.175 for 17.5%).

    Raises:
        ValueError: If tax_category is unknown or date cannot be parsed.
    """
    # Parse string date
    if isinstance(purchase_date, str):
        purchase_date = date.fromisoformat(purchase_date)

    if tax_category not in TAX_RATES:
        raise ValueError(f"Unknown tax category: {tax_category}")

    # GSYF/GYF holding duration override
    if (
        tax_category == TAX_CAT_GSYF_GYF_SHORT
        and holding_days is not None
        and holding_days > 730
    ):
        tax_category = TAX_CAT_GSYF_GYF_LONG

    period_idx = _find_period_index(purchase_date)
    rate_pct = TAX_RATES[tax_category][period_idx]
    return rate_pct / 100.0


def withholding_tax_rate(
    fund_code: str,
    purchase_date: date | str | None = None,
    holding_days: int | None = None,
) -> float | None:
    """Get the withholding tax rate for a specific fund.

    Convenience wrapper that fetches fund info from TEFAS, classifies the
    fund's tax category, and returns the applicable rate.

    Args:
        fund_code: TEFAS fund code (e.g., "AAK", "TTE").
        purchase_date: Date of fund purchase. Defaults to today.
        holding_days: Number of days held (relevant for GSYF/GYF funds).

    Returns:
        Tax rate as a decimal (e.g., 0.15 for 15%), or None if fund
        category cannot be determined.

    Examples:
        >>> import borsapy as bp
        >>> bp.withholding_tax_rate("AAK", "2025-06-01")
        0.15
        >>> bp.withholding_tax_rate("AAK", "2025-08-01")
        0.175
    """
    from borsapy.fund import Fund

    if purchase_date is None:
        purchase_date = date.today()

    fund = Fund(fund_code)
    info = fund.info
    category = info.get("category", "") or ""
    fund_name = info.get("name", "") or ""

    tax_cat = classify_fund_tax_category(category, fund_name)
    if tax_cat is None:
        return None

    return get_withholding_tax_rate(tax_cat, purchase_date, holding_days)


def withholding_tax_table() -> pd.DataFrame:
    """Return the full withholding tax reference table.

    Returns:
        DataFrame with columns: tax_category, description, and one column
        per date period showing the tax rate as a percentage.

    Examples:
        >>> import borsapy as bp
        >>> bp.withholding_tax_table()
           tax_category                  description  <23.12.2020  ...  >=09.07.2025
        0  degisken_karma_doviz  Degisken, karma, ...        10.0  ...          17.5
        1  pay_senedi_yogun      Pay senedi yogun fon         0.0  ...           0.0
        ...
    """
    period_labels = [
        "<23.12.2020",
        "23.12.2020-30.04.2024",
        "01.05.2024-31.10.2024",
        "01.11.2024-31.01.2025",
        "01.02.2025-08.07.2025",
        ">=09.07.2025",
    ]

    rows = []
    for cat in [
        TAX_CAT_VARIABLE,
        TAX_CAT_EQUITY_HEAVY,
        TAX_CAT_OTHER,
        TAX_CAT_GSYF_GYF_LONG,
        TAX_CAT_GSYF_GYF_SHORT,
    ]:
        row = {
            "tax_category": cat,
            "description": TAX_CAT_DESCRIPTIONS[cat],
        }
        for label, rate in zip(period_labels, TAX_RATES[cat], strict=True):
            row[label] = rate
        rows.append(row)

    return pd.DataFrame(rows)

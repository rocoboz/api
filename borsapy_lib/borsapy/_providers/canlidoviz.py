"""Canlidoviz.com provider for forex data - token-free alternative to doviz.com."""

import re
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL
from borsapy.exceptions import APIError, DataNotAvailableError


class CanlidovizProvider(BaseProvider):
    """
    Provider for forex data from canlidoviz.com.

    Key advantage: No authentication token required!

    Supports:
    - Currency history (USD, EUR, GBP, etc.)
    - Bank-specific currency rates and history
    - Precious metal rates (gram-altin, etc.)
    """

    API_BASE = "https://a.canlidoviz.com"
    WEB_BASE = "https://canlidoviz.com"

    # Main currency IDs (TRY prices) - 65 currencies
    # Discovered via Chrome DevTools network inspection on 2026-01-13
    CURRENCY_IDS = {
        # Major currencies
        "USD": 1,      # ABD Doları
        "EUR": 50,     # Euro
        "GBP": 100,    # İngiliz Sterlini
        "CHF": 51,     # İsviçre Frangı
        "CAD": 56,     # Kanada Doları
        "AUD": 102,    # Avustralya Doları
        "JPY": 57,     # 100 Japon Yeni
        "NZD": 67,     # Yeni Zelanda Doları
        "SGD": 17,     # Singapur Doları
        "HKD": 80,     # Hong Kong Doları
        "TWD": 9,      # Yeni Tayvan Doları
        # European currencies
        "DKK": 54,     # Danimarka Kronu
        "SEK": 60,     # İsveç Kronu
        "NOK": 99,     # Norveç Kronu
        "PLN": 110,    # Polonya Zlotisi
        "CZK": 69,     # Çek Korunası
        "HUF": 108,    # Macar Forinti
        "RON": 77,     # Romanya Leyi
        "BGN": 71,     # Bulgar Levası
        "HRK": 116,    # Hırvat Kunası
        "RSD": 7,      # Sırbistan Dinarı
        "BAM": 82,     # Bosna Hersek Markı
        "MKD": 21,     # Makedon Dinarı
        "ALL": 112,    # Arnavutluk Leki
        "MDL": 10,     # Moldovya Leusu
        "UAH": 8,      # Ukrayna Grivnası
        "BYR": 109,    # Belarus Rublesi
        "ISK": 83,     # İzlanda Kronası
        # Middle East & Africa
        "AED": 53,     # BAE Dirhemi
        "SAR": 61,     # Suudi Arabistan Riyali
        "QAR": 5,      # Katar Riyali
        "KWD": 104,    # Kuveyt Dinarı
        "BHD": 64,     # Bahreyn Dinarı
        "OMR": 2,      # Umman Riyali
        "JOD": 92,     # Ürdün Dinarı
        "IQD": 106,    # Irak Dinarı
        "IRR": 68,     # İran Riyali
        "LBP": 117,    # Lübnan Lirası
        "SYP": 6,      # Suriye Lirası
        "EGP": 111,    # Mısır Lirası
        "LYD": 101,    # Libya Dinarı
        "TND": 885,    # Tunus Dinarı
        "DZD": 88,     # Cezayir Dinarı
        "MAD": 89,     # Fas Dirhemi
        "ZAR": 59,     # Güney Afrika Randı
        "ILS": 63,     # İsrail Şekeli
        # Asia & Pacific
        "CNY": 107,    # Çin Yuanı
        "INR": 103,    # Hindistan Rupisi
        "PKR": 29,     # Pakistan Rupisi
        "LKR": 87,     # Sri Lanka Rupisi
        "IDR": 105,    # Endonezya Rupiahı
        "MYR": 3,      # Malezya Ringgiti
        "THB": 39,     # Tayland Bahtı
        "PHP": 4,      # Filipinler Pesosu
        "KRW": 113,    # Güney Kore Wonu
        "KZT": 85,     # Kazak Tengesi
        "AZN": 75,     # Azerbaycan Manatı
        "GEL": 162,    # Gürcistan Larisi
        # Americas
        "MXN": 65,     # Meksika Pesosu
        "BRL": 74,     # Brezilya Reali
        "ARS": 73,     # Arjantin Pesosu
        "CLP": 76,     # Şili Pesosu
        "COP": 114,    # Kolombiya Pesosu
        "PEN": 13,     # Peru İnti
        "UYU": 25,     # Uruguay Pesosu
        "CRC": 79,     # Kostarika Kolonu
        # Other
        "RUB": 97,     # Rus Rublesi
        "DVZSP1": 783, # Sepet Kur (Döviz Sepeti)
    }

    # Precious metal IDs (TRY prices)
    # Note: These IDs were verified against canlidoviz.com pages on 2026-01-13
    METAL_IDS = {
        "gram-altin": 32,       # ~6,300 TRY (altin-fiyatlari/gram-altin)
        "ceyrek-altin": 11,     # ~10,500 TRY
        "yarim-altin": 47,      # ~21,000 TRY
        "tam-altin": 14,        # ~42,000 TRY
        "cumhuriyet-altin": 27, # ~43,000 TRY
        "ata-altin": 43,        # ~43,000 TRY
        "gram-gumus": 20,       # ~115 TRY (altin-fiyatlari/gumus)
        "ons-altin": 81,        # ~104,000 TRY (ons in TRY)
        "gram-platin": 1012,    # ~3,260 TRY (emtia-fiyatlari/platin-gram)
    }

    # Energy IDs (USD prices)
    # Verified via Chrome DevTools network inspection on 2026-01-13
    ENERGY_IDS = {
        "BRENT": 266,           # Brent Petrol ~$64 (emtia-fiyatlari/brent-petrol)
    }

    # Commodity IDs - Precious metals in USD (emtia)
    # Verified via Chrome DevTools network inspection on 2026-01-13
    COMMODITY_IDS = {
        "XAG-USD": 267,         # Silver Ounce (emtia-fiyatlari/gumus-ons)
        "XPT-USD": 268,         # Platinum Spot (emtia-fiyatlari/platin-spot-dolar)
        "XPD-USD": 269,         # Palladium Spot (emtia-fiyatlari/paladyum-spot-dolar)
    }

    # Bank-specific USD IDs
    BANK_USD_IDS = {
        "akbank": 822,
        "garanti-bbva": 805,
        "is-bankasi": 1020,
        "ziraat-bankasi": 264,
        "halkbank": 1017,
        "yapi-kredi": 819,
        "vakifbank": 1018,
        "denizbank": 1019,
        "ing-bank": 1023,
        "hsbc": 1025,
        "teb": 1024,
        "qnb-finansbank": 788,
        "merkez-bankasi": 1016,
        "kapali-carsi": 1114,
        "kuveyt-turk": 1021,
        "albaraka-turk": 1022,
        "sekerbank": 1113,
        "enpara": 824,
    }

    # Bank-specific EUR IDs
    BANK_EUR_IDS = {
        "akbank": 1341,
        "garanti-bbva": 807,
        "is-bankasi": 1030,
        "ziraat-bankasi": 894,
        "merkez-bankasi": 1026,
        "halkbank": 1027,
        "yapi-kredi": 820,
        "vakifbank": 1028,
        "denizbank": 1029,
        "ing-bank": 1033,
        "hsbc": 1035,
        "teb": 1034,
        "qnb-finansbank": 789,
        "kapali-carsi": 1115,
        "kuveyt-turk": 1031,
        "albaraka-turk": 1032,
    }

    # Bank-specific GBP IDs (18 banka - halkbank hariç veri yok)
    BANK_GBP_IDS = {
        "akbank": 1342,
        "albaraka-turk": 1329,
        "denizbank": 1376,
        "destekbank": 1338,
        "fibabanka": 1410,
        "garanti-bbva": 809,
        "hsbc": 1417,
        "ing-bank": 1427,
        "is-bankasi": 1485,
        "kapali-carsi": 1116,
        "kuveyt-turk": 841,
        "merkez-bankasi": 1036,
        "qnb-finansbank": 791,
        "sekerbank": 1289,
        "teb": 1288,
        "vakifbank": 1460,
        "yapi-kredi": 1475,
        "ziraat-bankasi": 896,
    }

    # Bank-specific CHF IDs
    BANK_CHF_IDS = {
        "akbank": 1351,
        "albaraka-turk": 1330,
        "denizbank": 1377,
        "is-bankasi": 1489,
        "kapali-carsi": 1199,
        "merkez-bankasi": 1440,
        "vakifbank": 1461,
        "yapi-kredi": 1479,
        "ziraat-bankasi": 902,
    }

    # Bank-specific CAD IDs
    BANK_CAD_IDS = {
        "akbank": 1345,
        "is-bankasi": 1490,
        "kapali-carsi": 1204,
        "merkez-bankasi": 1442,
        "ziraat-bankasi": 899,
    }

    # Bank-specific AUD IDs
    BANK_AUD_IDS = {
        "akbank": 1343,
        "is-bankasi": 1486,
        "kapali-carsi": 1203,
        "merkez-bankasi": 1437,
        "ziraat-bankasi": 897,
    }

    # Bank-specific JPY IDs (100 Japon Yeni)
    BANK_JPY_IDS = {
        "garanti-bbva": 814,
        "kapali-carsi": 1198,
        "merkez-bankasi": 1455,
        "sekerbank": 1498,
        "vakifbank": 1469,
        "ziraat-bankasi": 1286,
    }

    # Bank-specific RUB IDs (Rus Rublesi)
    BANK_RUB_IDS = {
        "akbank": 1352,
        "albaraka-turk": 1367,
        "denizbank": 1384,
        "ing-bank": 1436,
        "kapali-carsi": 1206,
        "kuveyt-turk": 831,
        "merkez-bankasi": 1448,
        "qnb-finansbank": 801,
        "vakifbank": 1462,
        "ziraat-bankasi": 901,
    }

    # Bank-specific SAR IDs (Suudi Arabistan Riyali)
    BANK_SAR_IDS = {
        "akbank": 1350,
        "denizbank": 1401,
        "hsbc": 1418,
        "ing-bank": 1434,
        "is-bankasi": 1493,
        "kapali-carsi": 1205,
        "kuveyt-turk": 842,
        "merkez-bankasi": 1445,
        "qnb-finansbank": 802,
        "vakifbank": 1463,
        "yapi-kredi": 1483,
        "ziraat-bankasi": 903,
    }

    # Bank-specific AED IDs (BAE Dirhemi)
    BANK_AED_IDS = {
        "akbank": 1358,
        "denizbank": 1385,
        "kapali-carsi": 1208,
        "merkez-bankasi": 1454,
    }

    # Bank-specific CNY IDs (Çin Yuanı)
    BANK_CNY_IDS = {
        "akbank": 1353,
        "kapali-carsi": 1210,
        "merkez-bankasi": 1449,
    }

    # Bank slug to dovizcom-compatible slug mapping
    BANK_SLUG_MAP = {
        "akbank": "akbank",
        "albaraka-turk": "albaraka",
        "denizbank": "denizbank",
        "destekbank": "destekbank",
        "enpara": "enpara",
        "fibabanka": "fibabanka",
        "garanti-bbva": "garanti",
        "halkbank": "halkbank",
        "hsbc": "hsbc",
        "ing-bank": "ing",
        "is-bankasi": "isbank",
        "kapali-carsi": "kapalicarsi",
        "kuveyt-turk": "kuveytturk",
        "merkez-bankasi": "tcmb",
        "qnb-finansbank": "qnb",
        "sekerbank": "sekerbank",
        "teb": "teb",
        "vakifbank": "vakifbank",
        "yapi-kredi": "yapikredi",
        "ziraat-bankasi": "ziraat",
    }

    # Reverse mapping (dovizcom slug -> canlidoviz slug)
    DOVIZCOM_TO_CANLIDOVIZ = {v: k for k, v in BANK_SLUG_MAP.items()}

    # Currency code to URL slug mapping (for HTML scraping)
    CURRENCY_SLUGS = {
        "USD": "dolar",
        "EUR": "euro",
        "GBP": "ingiliz-sterlini",
        "CHF": "isvicre-frangi",
        "CAD": "kanada-dolari",
        "AUD": "avustralya-dolari",
        "JPY": "100-japon-yeni",
    }

    # Bank-specific metal IDs (gram-altin)
    # Verified via Chrome DevTools network inspection (January 2026)
    BANK_GRAM_ALTIN_IDS: dict[str, int] = {
        "kapali-carsi": 1115,
        "akbank": 823,
        "ziraat-bankasi": 1039,
        "is-bankasi": 1040,
        "vakifbank": 1037,
        "halkbank": 1036,
        "garanti-bankasi": 806,
        "yapi-kredi": 821,
        "denizbank": 1038,
        "albaraka": 1112,
        "destekbank": 1339,
        "enpara": 1041,
        "fibabanka": 1300,
        "hsbc": 1045,
        "ing-bank": 1043,
        "kuveyt-turk": 826,
        "qnb-finansbank": 789,
        "sekerbank": 1042,
        "teb": 1044,
    }

    # Bank-specific metal IDs (gumus/silver)
    # Verified via Chrome DevTools network inspection (January 2026)
    BANK_GUMUS_IDS: dict[str, int] = {
        "kapali-carsi": 1181,
        "akbank": 1359,
        "albaraka": 1372,
        "denizbank": 1378,
        "destekbank": 1340,
        "fibabanka": 1413,
        "garanti-bankasi": 1415,
        "halkbank": 1416,
        "hsbc": 1426,
        "kuveyt-turk": 827,
        "qnb-finansbank": 1456,
        "vakifbank": 1474,
        "ziraat-bankasi": 1283,
    }

    # Bank-specific metal IDs (platin/platinum)
    # Verified via Chrome DevTools network inspection (January 2026)
    # Note: Only Kuveyt Türk provides platin institution rates on canlidoviz
    BANK_PLATIN_IDS: dict[str, int] = {
        "kuveyt-turk": 1013,
    }

    def __init__(self):
        super().__init__()

    def _get_headers(self) -> dict[str, str]:
        """Get request headers - no token needed!"""
        return {
            "Accept": "*/*",
            "Origin": self.WEB_BASE,
            "Referer": f"{self.WEB_BASE}/",
            "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
        }

    def _get_item_id(
        self, asset: str, institution: str | None = None
    ) -> int | None:
        """
        Get canlidoviz item ID for an asset.

        Args:
            asset: Currency code (USD, EUR) or metal (gram-altin).
            institution: Optional bank/institution slug.

        Returns:
            Item ID or None if not found.
        """
        asset_upper = asset.upper()

        if institution:
            # Convert dovizcom slug to canlidoviz slug if needed
            inst_slug = self.DOVIZCOM_TO_CANLIDOVIZ.get(institution, institution)

            # Bank-specific ID
            if asset_upper == "USD":
                return self.BANK_USD_IDS.get(inst_slug)
            elif asset_upper == "EUR":
                return self.BANK_EUR_IDS.get(inst_slug)
            elif asset_upper == "GBP":
                return self.BANK_GBP_IDS.get(inst_slug)
            elif asset_upper == "CHF":
                return self.BANK_CHF_IDS.get(inst_slug)
            elif asset_upper == "CAD":
                return self.BANK_CAD_IDS.get(inst_slug)
            elif asset_upper == "AUD":
                return self.BANK_AUD_IDS.get(inst_slug)
            elif asset_upper == "JPY":
                return self.BANK_JPY_IDS.get(inst_slug)
            elif asset_upper == "RUB":
                return self.BANK_RUB_IDS.get(inst_slug)
            elif asset_upper == "SAR":
                return self.BANK_SAR_IDS.get(inst_slug)
            elif asset_upper == "AED":
                return self.BANK_AED_IDS.get(inst_slug)
            elif asset_upper == "CNY":
                return self.BANK_CNY_IDS.get(inst_slug)
            elif asset == "gram-altin":
                return self.BANK_GRAM_ALTIN_IDS.get(inst_slug)
            elif asset == "gumus":
                return self.BANK_GUMUS_IDS.get(inst_slug)
            elif asset == "gram-platin":
                return self.BANK_PLATIN_IDS.get(inst_slug)
            return None

        # Main asset ID
        if asset_upper in self.CURRENCY_IDS:
            return self.CURRENCY_IDS[asset_upper]
        if asset in self.METAL_IDS:
            return self.METAL_IDS[asset]
        if asset_upper in self.ENERGY_IDS:
            return self.ENERGY_IDS[asset_upper]
        if asset_upper in self.COMMODITY_IDS:
            return self.COMMODITY_IDS[asset_upper]

        return None

    def get_history(
        self,
        asset: str,
        period: str = "1mo",
        start: datetime | None = None,
        end: datetime | None = None,
        institution: str | None = None,
    ) -> pd.DataFrame:
        """
        Get historical OHLC data for a currency or metal.

        Args:
            asset: Currency code (USD, EUR) or metal (gram-altin).
            period: Period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y).
            start: Start date. Overrides period if provided.
            end: End date. Defaults to now.
            institution: Optional bank slug for bank-specific history.

        Returns:
            DataFrame with OHLC data indexed by Date.

        Raises:
            DataNotAvailableError: If asset is not supported.
            APIError: If API request fails.
        """
        item_id = self._get_item_id(asset, institution)
        if item_id is None:
            if institution:
                raise DataNotAvailableError(
                    f"No canlidoviz data for {asset} from {institution}"
                )
            raise DataNotAvailableError(f"Unsupported asset: {asset}")

        # Calculate date range
        end_dt = end or datetime.now()
        if start:
            start_dt = start
        else:
            days = {
                "1d": 1,
                "5d": 5,
                "1mo": 30,
                "3mo": 90,
                "6mo": 180,
                "1y": 365,
                "2y": 730,
                "5y": 1825,
                "max": 3650,
            }.get(period, 30)
            start_dt = end_dt - timedelta(days=days)

        cache_key = f"canlidoviz:history:{asset}:{institution}:{start_dt.date()}:{end_dt.date()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            url = f"{self.API_BASE}/items/history"
            params = {
                "period": "DAILY",
                "itemDataId": item_id,
                "startDate": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "endDate": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            }

            response = self._client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()

            # Parse response: {"timestamp": "open|high|low|close", ...}
            records = []
            for ts_str, ohlc_str in data.items():
                try:
                    ts = int(ts_str)
                    dt = datetime.fromtimestamp(ts)
                    values = ohlc_str.split("|")
                    if len(values) >= 4:
                        records.append({
                            "Date": dt,
                            "Open": float(values[0]),
                            "High": float(values[1]),
                            "Low": float(values[2]),
                            "Close": float(values[3]),
                        })
                except (ValueError, IndexError):
                    continue

            df = pd.DataFrame(records)
            if not df.empty:
                df.set_index("Date", inplace=True)
                df.sort_index(inplace=True)

            self._cache_set(cache_key, df, TTL.OHLCV_HISTORY)
            return df

        except Exception as e:
            raise APIError(f"Failed to fetch canlidoviz history for {asset}: {e}") from e

    def get_current(self, asset: str, institution: str | None = None) -> dict[str, Any]:
        """
        Get current price for a currency or metal.

        Uses the most recent data point from history API.

        Args:
            asset: Currency code (USD, EUR) or metal (gram-altin).
            institution: Optional bank slug for bank-specific rate.

        Returns:
            Dictionary with current price data.
        """
        item_id = self._get_item_id(asset, institution)
        if item_id is None:
            raise DataNotAvailableError(f"Unsupported asset: {asset}")

        cache_key = f"canlidoviz:current:{asset}:{institution}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        try:
            # Get recent history to extract latest price
            df = self.get_history(asset, period="5d", institution=institution)

            if df.empty:
                raise DataNotAvailableError(f"No data for {asset}")

            # Get the most recent row
            latest = df.iloc[-1]
            latest_date = df.index[-1]

            result = {
                "symbol": asset,
                "last": float(latest["Close"]),
                "open": float(latest["Open"]),
                "high": float(latest["High"]),
                "low": float(latest["Low"]),
                "update_time": latest_date,
            }

            if institution:
                result["institution"] = institution

            self._cache_set(cache_key, result, TTL.FX_RATES)
            return result

        except Exception as e:
            raise APIError(f"Failed to fetch current price for {asset}: {e}") from e

    def get_supported_currencies(self) -> list[str]:
        """Get list of supported currencies."""
        return sorted(self.CURRENCY_IDS.keys())

    def get_supported_metals(self) -> list[str]:
        """Get list of supported metals."""
        return sorted(self.METAL_IDS.keys())

    def get_supported_banks(self, currency: str = "USD") -> list[str]:
        """
        Get list of supported banks for a currency.

        Args:
            currency: Currency code (default USD).

        Returns:
            List of bank slugs.
        """
        currency = currency.upper()
        if currency == "USD":
            return sorted(self.BANK_USD_IDS.keys())
        elif currency == "EUR":
            return sorted(self.BANK_EUR_IDS.keys())
        elif currency == "GBP":
            return sorted(self.BANK_GBP_IDS.keys())
        elif currency == "CHF":
            return sorted(self.BANK_CHF_IDS.keys())
        elif currency == "CAD":
            return sorted(self.BANK_CAD_IDS.keys())
        elif currency == "AUD":
            return sorted(self.BANK_AUD_IDS.keys())
        elif currency == "JPY":
            return sorted(self.BANK_JPY_IDS.keys())
        elif currency == "RUB":
            return sorted(self.BANK_RUB_IDS.keys())
        elif currency == "SAR":
            return sorted(self.BANK_SAR_IDS.keys())
        elif currency == "AED":
            return sorted(self.BANK_AED_IDS.keys())
        elif currency == "CNY":
            return sorted(self.BANK_CNY_IDS.keys())
        return []

    def get_bank_rates(
        self, currency: str, bank: str | None = None
    ) -> pd.DataFrame | dict[str, Any]:
        """
        Get buy/sell rates from banks via HTML scraping.

        Args:
            currency: Currency code (USD, EUR, GBP, etc.)
            bank: Optional bank slug. If provided, returns single dict.

        Returns:
            DataFrame with all banks or dict for single bank.
            Columns: bank, bank_name, currency, buy, sell, spread

        Raises:
            DataNotAvailableError: If currency is not supported.
        """
        currency = currency.upper()
        slug = self.CURRENCY_SLUGS.get(currency)
        if not slug:
            raise DataNotAvailableError(
                f"Bank rates not available for {currency}. "
                f"Supported: {list(self.CURRENCY_SLUGS.keys())}"
            )

        cache_key = f"canlidoviz:bank_rates:{currency}"
        cached = self._cache_get(cache_key)

        if cached is None:
            url = f"{self.WEB_BASE}/doviz-kurlari/{slug}"
            try:
                response = self._client.get(url, headers=self._get_headers())
                response.raise_for_status()
                html = response.text
                cached = self._parse_bank_rates_html(html, currency)
                self._cache_set(cache_key, cached, TTL.FX_RATES)
            except Exception as e:
                raise APIError(f"Failed to fetch bank rates: {e}") from e

        if bank:
            # Convert dovizcom slug to canlidoviz slug
            bank_slug = self.DOVIZCOM_TO_CANLIDOVIZ.get(bank, bank)
            for row in cached:
                if row["bank"] == bank_slug:
                    return row
            raise DataNotAvailableError(f"Bank {bank} not found for {currency}")

        return pd.DataFrame(cached)

    def _parse_bank_rates_html(
        self, html: str, currency: str
    ) -> list[dict[str, Any]]:
        """Parse bank rates from HTML page.

        HTML structure: Each bank is in a table row with TDs:
        - TD 0: Bank name link
        - TD 1: Buy price (Alış)
        - TD 2: Sell price + change values concatenated (Satış0.54%-1.21)
        - TD 3: Close (Kapanış)
        - TD 4: High (Yüksek)
        - TD 5: Low (Düşük)
        """
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Find all bank links in the "DİĞER PİYASALAR" table
        # Pattern: /doviz-kurlari/{bank-slug}/{currency-slug}
        currency_slug = self.CURRENCY_SLUGS.get(currency.upper(), "")
        pattern = re.compile(rf"/doviz-kurlari/([^/]+)/{currency_slug}$")

        for link in soup.find_all("a", href=pattern):
            match = pattern.search(link.get("href", ""))
            if not match:
                continue

            bank_slug = match.group(1)
            # Skip the main currency page link
            if bank_slug == currency_slug:
                continue

            # Get bank display name from link text
            bank_text = link.get_text(strip=True)
            # Remove timestamp if present (e.g., "AKBANK15:57:42" or "AKBANK 15:57:42")
            bank_name = re.sub(r"\s*\d{2}:\d{2}:\d{2}$", "", bank_text)

            # Find the parent TD element
            td_parent = link.find_parent("td")
            if not td_parent:
                continue

            # Get sibling TDs containing the values
            sibling_tds = td_parent.find_next_siblings("td")
            if len(sibling_tds) < 2:
                continue

            try:
                # TD 0: Buy price (clean number like "42.4400")
                buy_text = sibling_tds[0].get_text(strip=True)
                buy = float(buy_text.replace(",", "."))

                # TD 1: Sell price + change concatenated (e.g., "43.79000.54%-1.21")
                # Extract the first decimal number (sell price)
                sell_text = sibling_tds[1].get_text(strip=True)
                sell_match = re.match(r"^(\d+[.,]\d+)", sell_text)
                if not sell_match:
                    continue
                sell = float(sell_match.group(1).replace(",", "."))

                spread = round((sell - buy) / buy * 100, 2) if buy > 0 else 0

                results.append({
                    "bank": bank_slug,
                    "bank_name": bank_name,
                    "currency": currency,
                    "buy": buy,
                    "sell": sell,
                    "spread": spread,
                })
            except (ValueError, IndexError, AttributeError):
                continue

        return results


# Singleton
_provider: CanlidovizProvider | None = None


def get_canlidoviz_provider() -> CanlidovizProvider:
    """Get singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = CanlidovizProvider()
    return _provider

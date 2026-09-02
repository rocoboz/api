from __future__ import annotations

import json

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query, Request, Response

from api_core.services.cache import get_cached_market, get_cached_realtime, get_cached_static
from api_core.services.enrichers import enrich_stock_row, enrich_stock_rows
from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json
from api_core.services.providers import Ticker, Fund, Index, get_kap_provider, market
from api_core.services.response import api_ok, pagination_meta
from api_core.services.security import limiter

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/list")
@limiter.limit("30/minute")
def list_stocks(request: Request, response: Response, limit: int = 50, offset: int = 0, envelope: bool = False):
    def fetch():
        try:
            df = market.companies()
            if df.empty:
                return []
            sliced = df.iloc[offset : offset + limit]
            return enrich_stock_rows(df_to_json(sliced))
        except Exception:
            return []

    rows = get_cached_static(f"ST_LIST_V2_{limit}_{offset}", fetch)
    meta = pagination_meta(limit=limit, offset=offset, count=len(rows))
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)
    response.headers["X-Count"] = str(len(rows))
    return api_ok(rows, meta) if envelope else rows


@router.get("/compare")
@limiter.limit("20/minute")
def compare(request: Request, response: Response, symbols: str = Query(...), envelope: bool = False):
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    def fetch():
        return [enrich_stock_row({"symbol": symbol, "name": symbol}) for symbol in sym_list]

    rows = get_cached_market(f"COMPARE_{symbols}", fetch)
    meta = {"count": len(rows), "symbols": sym_list}
SECTOR_DEFINITIONS = {
    "banka": {
        "index": "XBANK",
        "name": "BIST Banka",
        "description": "Bankacılık ve Finansal Hizmetler",
        "fallback": ["AKBNK", "GARAN", "ISCTR", "YKBNK", "HALKB", "VAKBN", "ALBRK", "SKBNK", "KLNMA", "TSKB", "ICBCT", "QNBFB"],
    },
    "sanayi": {
        "index": "XUSIN",
        "name": "BIST Sınai",
        "description": "Sanayi, Üretim ve İmalat Şirketleri",
        "fallback": ["EREGL", "FROTO", "TOASO", "TUPRS", "ARCLK", "ASELS", "SISE", "PETKM", "KRDMD", "BRISA", "OTKAR"],
    },
    "holding": {
        "index": "XHOLD",
        "name": "BIST Holding",
        "description": "Holding ve Yatırım Kuruluşları",
        "fallback": ["KCHOL", "SAHOL", "SISE", "DOHOL", "TKFEN", "AGHOL", "ENKAI", "BERA", "GLYHO", "GSDHO"],
    },
    "teknoloji": {
        "index": "XUTEK",
        "name": "BIST Teknoloji",
        "description": "Bilişim, Yazılım ve Savunma Teknolojileri",
        "fallback": ["ASELS", "KFEIN", "VBTYZ", "MIATK", "SMART", "LOGO", "ARDYZ", "FONET", "SDTTR", "REEDR", "PATEK"],
    },
    "ulastirma": {
        "index": "XULAS",
        "name": "BIST Ulaştırma",
        "description": "Havacılık, Lojistik, Kara ve Deniz Taşımacılığı",
        "fallback": ["THYAO", "PGSUS", "TAVHL", "CLEBI", "RYSAS", "GSDHO"],
    },
    "enerji": {
        "index": "XELKT",
        "name": "BIST Elektrik & Enerji",
        "description": "Yenilenebilir ve Konvansiyonel Enerji Üretimi",
        "fallback": ["AKSEN", "ENJSA", "CWENE", "ASTOR", "EUPWR", "ALFAK", "GESAN", "SMRTG", "CANTE", "ZOREN", "AYDEM", "GWIND", "ODAS"],
    },
    "gida": {
        "index": "XGIDA",
        "name": "BIST Gıda & Perakende",
        "description": "Gıda Üretimi, Tarım ve Zincir Marketler",
        "fallback": ["BIMAS", "SOKM", "MGROS", "CCOLA", "AEFES", "ULKER", "TATGD", "KUTPO", "PETUN", "PNSUT"],
    },
    "gmyo": {
        "index": "XGMYO",
        "name": "BIST GYO",
        "description": "Gayrimenkul Yatırım Ortaklıkları",
        "fallback": ["EKGYO", "TRGYO", "ISGYO", "SNGYO", "KZGYO", "AVPGY", "OZKGY", "VKGYO", "KLGYO", "DAPGM", "PEKGY"],
    },
    "kimya": {
        "index": "XKMYA",
        "name": "BIST Kimya, Petrol & Plastik",
        "description": "Petrokimya, Gübre, Boya ve Plastik",
        "fallback": ["TUPRS", "PETKM", "SASA", "HEKTS", "KORDS", "BAGFS", "GUBRF", "EGGUB", "DYOBY"],
    },
    "iletisim": {
        "index": "XILTM",
        "name": "BIST İletişim",
        "description": "Telekomünikasyon ve Haberleşme",
        "fallback": ["TCELL", "TTKOM"],
    },
    "maden": {
        "index": "XMADN",
        "name": "BIST Madencilik",
        "description": "Maden Çıkarma ve Doğal Kaynaklar",
        "fallback": ["KOZAL", "KOZAA", "IPEKE", "PRKME"],
    },
    "metal": {
        "index": "XMANA",
        "name": "BIST Metal Ana",
        "description": "Demir, Çelik ve Metalurji Sanayi",
        "fallback": ["EREGL", "KRDMD", "KRDMA", "KRDMB", "ISDMR", "CEMTS", "BRSAN", "BMSCH", "TUCLK"],
    },
    "sigorta": {
        "index": "XSGRT",
        "name": "BIST Sigorta",
        "description": "Sigorta ve Bireysel Emeklilik",
        "fallback": ["ANSGR", "AKGRT", "TURSG", "AGESA", "RAYSG"],
    },
    "turizm": {
        "index": "XTRZM",
        "name": "BIST Turizm",
        "description": "Turizm, Otelcilik ve Eğlence",
        "fallback": ["AYCES", "MAALT", "PKENT", "TEKTU", "ULAS"],
    },
    "tekstil": {
        "index": "XTEKS",
        "name": "BIST Tekstil",
        "description": "Tekstil, Giyim ve Deri Üretimi",
        "fallback": ["MNDRS", "BOSSA", "KORDS", "YUNSA", "ARSAN", "DESA"],
    },
    "spor": {
        "index": "XSPOR",
        "name": "BIST Spor",
        "description": "Spor Kulüpleri ve Sportif Faaliyetler",
        "fallback": ["BJKAS", "FENER", "GSRAY", "TSPOR"],
    },
    "katilim": {
        "index": "XKTUM",
        "name": "BIST Katılım Tüm",
        "description": "Faizsiz Finans / Katılım Esaslarına Uygun Hisseler",
        "fallback": ["BIMAS", "THYAO", "ASELS", "EREGL", "FROTO", "TUPRS", "ENJSA", "ASTOR", "KCHOL"],
    },
}


@router.get("/sectors")
@limiter.limit("30/minute")
def list_sectors(request: Request, response: Response):
    """Return all available Borsa Istanbul (BIST) sector classifications with index codes and descriptions."""
    sectors_list = [
        {
            "slug": slug,
            "index_code": data["index"],
            "name": data["name"],
            "description": data["description"],
            "url": f"/stocks/sectors/{slug}",
        }
        for slug, data in SECTOR_DEFINITIONS.items()
    ]
    return {
        "count": len(sectors_list),
        "sectors": sectors_list,
    }


@router.get("/sectors/{sector}")
@limiter.limit("30/minute")
def get_sector_stocks(request: Request, response: Response, sector: str, envelope: bool = False):
    """Return all constituent stocks for a specific sector with live quotes."""
    sec_key = sector.lower().strip()
    matched_entry = None
    if sec_key in SECTOR_DEFINITIONS:
        matched_entry = SECTOR_DEFINITIONS[sec_key]
    else:
        for k, v in SECTOR_DEFINITIONS.items():
            if v["index"].lower() == sec_key or k == sec_key:
                matched_entry = v
                break

    if not matched_entry:
        return {
            "error": f"Sector '{sector}' not found. Available sectors: {list(SECTOR_DEFINITIONS.keys())}"
        }

    index_code = matched_entry["index"]

    def fetch():
        companies = []
        try:
            idx = Index(index_code)
            comps = idx.components
            if comps:
                companies = [c["symbol"] for c in comps]
        except Exception:
            pass

        if not companies:
            companies = matched_entry["fallback"]

        stock_list = [{"symbol": s, "name": s} for s in companies]
        return {
            "sector": sec_key,
            "index_code": index_code,
            "name": matched_entry["name"],
            "description": matched_entry["description"],
            "company_count": len(stock_list),
            "companies": stock_list,
        }

    data = get_cached_static(f"SECTOR_COMPONENTS_{index_code}", fetch)
    return api_ok(data) if envelope else data


@router.get("/movers")
@limiter.limit("30/minute")
def get_market_movers(request: Request, response: Response, limit: int = Query(5, ge=1, le=20)):
    """Return top gaining, losing, and most actively traded BIST stocks of the day."""
    def fetch():
        try:
            from tradingview_screener import Query as TvQuery

            q = TvQuery().set_markets("turkey").select("name", "close", "change", "volume")
            _, df = q.get_scanner_data()
            if df.empty:
                return {"count": 0, "gainers": [], "losers": [], "most_active": []}

            df = df.dropna(subset=["change", "close", "volume"])
            gainers = [
                {"symbol": r["name"], "price": float(r["close"]), "change_percent": round(float(r["change"]), 2), "volume": float(r["volume"])}
                for _, r in df.sort_values("change", ascending=False).head(limit).iterrows()
            ]
            losers = [
                {"symbol": r["name"], "price": float(r["close"]), "change_percent": round(float(r["change"]), 2), "volume": float(r["volume"])}
                for _, r in df.sort_values("change", ascending=True).head(limit).iterrows()
            ]
            most_active = [
                {"symbol": r["name"], "price": float(r["close"]), "change_percent": round(float(r["change"]), 2), "volume": float(r["volume"])}
                for _, r in df.sort_values("volume", ascending=False).head(limit).iterrows()
            ]

            return {
                "count": limit,
                "gainers": gainers,
                "losers": losers,
                "most_active": most_active
            }
        except Exception as exc:
            return {"error": str(exc), "count": 0, "gainers": [], "losers": [], "most_active": []}

    return get_cached_market(f"STOCKS_MOVERS_{limit}", fetch)


@router.get("/indices/{code}")
@limiter.limit("30/minute")
def get_index_constituents(request: Request, response: Response, code: str, envelope: bool = False):
    """Return constituent stocks of standard BIST indices (e.g. XU030, XU050, XU100, XKTUM)."""
    idx_code = code.upper().strip()
    aliases = {
        "BIST30": "XU030", "XU30": "XU030",
        "BIST50": "XU050", "XU50": "XU050",
        "BIST100": "XU100", "XU100": "XU100",
        "BISTKATILIM": "XKTUM", "KATILIM": "XKTUM"
    }
    resolved = aliases.get(idx_code, idx_code)

    def fetch():
        try:
            idx = Index(resolved)
            comps = idx.components
            if not comps:
                return {"index_code": resolved, "count": 0, "companies": [], "error": f"Components not found for index {resolved}"}

            companies = [{"symbol": c["symbol"], "name": c.get("name", c["symbol"])} for c in comps]
            idx_name = resolved
            try:
                idx_name = idx.info.get("name", resolved)
            except Exception:
                pass
            return {
                "index_code": resolved,
                "index_name": idx_name,
                "count": len(companies),
                "companies": companies,
            }
        except Exception as exc:
            return {"index_code": resolved, "error": str(exc)}

    data = get_cached_static(f"INDEX_COMPONENTS_{resolved}", fetch)
    return api_ok(data) if envelope else data


BIST_HIGH_DIVIDEND_STOCKS = [
    {"symbol": "DOAS", "name": "Doğuş Otomotiv", "dividend_yield": 8.40, "net_dividend": 22.50, "gross_dividend": 25.00, "payout_ratio": 70.0, "status": "CONFIRMED"},
    {"symbol": "FROTO", "name": "Ford Otomotiv", "dividend_yield": 7.15, "net_dividend": 43.30, "gross_dividend": 48.11, "payout_ratio": 72.5, "status": "CONFIRMED"},
    {"symbol": "TUPRS", "name": "Tüpraş", "dividend_yield": 6.90, "net_dividend": 10.74, "gross_dividend": 11.93, "payout_ratio": 68.0, "status": "CONFIRMED"},
    {"symbol": "TTRAK", "name": "Türk Traktör", "dividend_yield": 6.20, "net_dividend": 56.66, "gross_dividend": 62.96, "payout_ratio": 80.0, "status": "CONFIRMED"},
    {"symbol": "TOASO", "name": "Tofaş Oto. Fab.", "dividend_yield": 6.10, "net_dividend": 18.00, "gross_dividend": 20.00, "payout_ratio": 65.0, "status": "CONFIRMED"},
    {"symbol": "EREGL", "name": "Ereğli Demir Çelik", "dividend_yield": 5.80, "net_dividend": 0.45, "gross_dividend": 0.50, "payout_ratio": 55.0, "status": "CONFIRMED"},
    {"symbol": "AYGAZ", "name": "Aygaz", "dividend_yield": 5.40, "net_dividend": 6.16, "gross_dividend": 6.85, "payout_ratio": 60.0, "status": "CONFIRMED"},
    {"symbol": "ISDMR", "name": "İskenderun Demir Çelik", "dividend_yield": 5.20, "net_dividend": 0.45, "gross_dividend": 0.50, "payout_ratio": 50.0, "status": "CONFIRMED"},
    {"symbol": "ENKAI", "name": "Enka İnşaat", "dividend_yield": 4.10, "net_dividend": 1.25, "gross_dividend": 1.39, "payout_ratio": 45.0, "status": "CONFIRMED"},
    {"symbol": "BIMAS", "name": "BİM Birleşik Mağazalar", "dividend_yield": 3.80, "net_dividend": 8.50, "gross_dividend": 9.44, "payout_ratio": 50.0, "status": "CONFIRMED"},
]


@router.get("/dividends/top")
@limiter.limit("30/minute")
def get_top_dividend_stocks(request: Request, response: Response, limit: int = Query(10, ge=1, le=50), envelope: bool = False):
    """Return top dividend-paying BIST companies ranked by dividend yield."""
    def fetch():
        data = sorted(BIST_HIGH_DIVIDEND_STOCKS, key=lambda x: x["dividend_yield"], reverse=True)[:limit]
        return {
            "count": len(data),
            "description": "BIST En Yüksek Temettü Verimine Sahip Şirketler",
            "top_dividends": data,
        }

    data = get_cached_static(f"TOP_DIVIDENDS_{limit}", fetch)
    return api_ok(data) if envelope else data


@router.get("/dividends/calendar")
@limiter.limit("30/minute")
def get_dividend_calendar(request: Request, response: Response, envelope: bool = False):
    """Return Borsa Istanbul upcoming and declared dividend distribution calendar."""
    def fetch():
        items = [
            {
                "symbol": s["symbol"],
                "name": s["name"],
                "net_dividend": s["net_dividend"],
                "gross_dividend": s["gross_dividend"],
                "dividend_yield": s["dividend_yield"],
                "status": s["status"],
            }
            for s in BIST_HIGH_DIVIDEND_STOCKS
        ]
        return {
            "count": len(items),
            "calendar": items,
        }

    data = get_cached_static("DIVIDEND_CALENDAR_ALL", fetch)
    return api_ok(data) if envelope else data


@router.get("/{symbol}")
@limiter.limit("30/minute")
def get_stock(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        tk = Ticker(symbol)
        try:
            info = dict(tk.fast_info) if hasattr(tk, "fast_info") else dict(tk.info)
        except Exception:
            info = dict(tk.info)

        def fetch_kap():
            try:
                kap = get_kap_provider()
                return kap.get_company_details(symbol)
            except Exception:
                return {}

        info["details"] = get_cached_static(f"KAP_DETAILS_{symbol}", fetch_kap)
        return compact_payload({"symbol": symbol, "data": info})

    return get_cached_market(f"STOCK_{symbol}", fetch)


@router.get("/{symbol}/history")
@limiter.limit("30/minute")
def get_history(request: Request, response: Response, symbol: str, period: str = "1mo", interval: str = "1d", asset_type: str | None = None):
    symbol = symbol.upper()

    def fetch():
        # Use explicit asset_type if provided, otherwise default to stock
        is_fund = asset_type == "fund" if asset_type else False
        if is_fund:
            obj = Fund(symbol)
            df = obj.history(period=period)
        else:
            obj = Ticker(symbol)
            df = obj.history(period=period, interval=interval)
        if df.empty:
            return {"error": "No data"}
        return df_to_json(df)

    return get_cached_realtime(f"HIST_{symbol}_{period}_{interval}_{asset_type}", fetch)


@router.get("/{symbol}/depth")
@limiter.limit("10/minute")
def get_simulated_depth(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        tk = Ticker(symbol)
        hist = tk.history(period="1d", interval="5m")
        if hist.empty:
            return {"error": "Insufficient intraday data"}

        low, high = hist["Low"].min(), hist["High"].max()
        if high == low:
            high += 0.01

        bins = np.linspace(low, high, 20)
        hist["PriceBin"] = pd.cut(hist["Close"], bins=bins, labels=bins[:-1])
        vp = hist.groupby("PriceBin", observed=False)["Volume"].sum().reset_index()
        vp = vp.dropna().sort_values("PriceBin", ascending=False)
        total_vol = vp["Volume"].sum()
        result = []
        for _, row in vp.iterrows():
            result.append(
                {
                    "price": round(float(row["PriceBin"]), 2),
                    "volume": int(row["Volume"]),
                    "weight": round((row["Volume"] / total_vol) * 100, 1),
                }
            )
        return {"symbol": symbol, "simulated_depth": result, "method": "Volume-at-Price Profile"}

    return get_cached_realtime(f"DEPTH_{symbol}", fetch)


@router.get("/{symbol}/disclosures")
@limiter.limit("15/minute")
def get_disclosures(request: Request, response: Response, symbol: str, limit: int = 15):
    def fetch():
        kap = get_kap_provider()
        return df_to_json(kap.get_disclosures(symbol, limit))

    return get_cached_market(f"DISC_{symbol}_{limit}", fetch)


@router.get("/{symbol}/dividends")
@limiter.limit("20/minute")
def get_dividends(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        try:
            tk = Ticker(symbol)
            divs = tk.dividends
            if divs is None or divs.empty:
                return []
            df = divs.reset_index()
            df = df.rename(columns={"Date": "date", "Amount": "amount", "GrossRate": "gross", "NetRate": "net"})
            return df_to_json(df)
        except Exception:
            return []

    return get_cached_static(f"DIVS_{symbol}", fetch)


@router.get("/{symbol}/financials")
@limiter.limit("20/minute")
def get_financials(request: Request, response: Response, symbol: str, type: str = "income"):
    symbol = symbol.upper()

    def fetch():
        try:
            tk = Ticker(symbol)
            if type == "balance":
                df = tk.balance_sheet
            elif type == "cash":
                df = tk.cash_flow
            else:
                df = tk.income_stmt
            if df is None or df.empty:
                return {"error": "No data"}
            return compact_payload(json.loads(df.to_json(date_format="iso")))
        except Exception:
            return {"error": "Financial data currently unavailable"}

    return get_cached_static(f"FIN_{symbol}_{type}", fetch)


@router.get("/{symbol}/recommendations")
@limiter.limit("20/minute")
def get_recommendations(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        try:
            tk = Ticker(symbol)
            try:
                targets = tk.analyst_price_targets
            except Exception:
                targets = {}
            try:
                summary = tk.recommendations_summary
            except Exception:
                summary = {}
            try:
                rec = tk.recommendations
            except Exception:
                rec = {}
            return compact_payload({
                "symbol": symbol,
                "targets": {k: clean_json_val(v) for k, v in targets.items()},
                "summary": {k: clean_json_val(v) for k, v in summary.items()},
                "overall": {k: clean_json_val(v) for k, v in rec.items()}
            })
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_static(f"REC_{symbol}", fetch)


@router.get("/{symbol}/holders")
@limiter.limit("20/minute")
def get_major_holders(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        try:
            tk = Ticker(symbol)
            df = tk.major_holders
            if df.empty:
                return []
            return df_to_json(df.reset_index())
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_static(f"HOLDERS_{symbol}", fetch)


@router.get("/{symbol}/etfs")
@limiter.limit("20/minute")
def get_etf_holders(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        try:
            tk = Ticker(symbol)
            df = tk.etf_holders
            if df.empty:
                return []
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_static(f"ETFS_{symbol}", fetch)


@router.get("/{symbol}/calendar")
@limiter.limit("20/minute")
def get_stock_calendar(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        try:
            tk = Ticker(symbol)
            try:
                cal_df = tk.calendar
                cal = df_to_json(cal_df) if not cal_df.empty else []
            except Exception:
                cal = []
            try:
                earn_df = tk.earnings_dates
                earn = df_to_json(earn_df.reset_index()) if not earn_df.empty else []
            except Exception:
                earn = []
            return compact_payload({
                "symbol": symbol,
                "calendar": cal,
                "earnings_dates": earn
            })
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_static(f"CAL_{symbol}", fetch)


def _find_item_val(df: pd.DataFrame | None, keywords: list[str], col_idx: int = 0) -> float | None:
    if df is None or df.empty or col_idx >= len(df.columns):
        return None
    for idx_label in df.index:
        label_str = str(idx_label).lower()
        if any(k in label_str for k in keywords):
            try:
                val = float(df.iloc[df.index.get_loc(idx_label), col_idx])
                if not pd.isna(val):
                    return val
            except (ValueError, TypeError):
                continue
    return None


@router.get("/{symbol}/health")
@limiter.limit("20/minute")
def get_stock_health(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        try:
            tk = Ticker(symbol)
            info = tk.info or {}

            try:
                bs = tk.balance_sheet
            except Exception:
                bs = None
            try:
                inc = tk.income_stmt
            except Exception:
                inc = None
            try:
                cf = tk.cashflow
            except Exception:
                cf = None

            signals = []
            score = 0
            max_points = 0

            # 1. Net Income > 0
            net_inc_cur = _find_item_val(inc, ["dönem karı", "net kar", "net profit"], 0)
            if net_inc_cur is not None:
                max_points += 1
                passed = net_inc_cur > 0
                if passed:
                    score += 1
                signals.append({
                    "id": "net_income_positive",
                    "category": "Karlılık",
                    "title": "Pozitif Net Kâr",
                    "passed": bool(passed),
                    "detail": f"Son dönem net kârı pozitif ({round(net_inc_cur, 2)})" if passed else "Son dönemde net zarar açıklandı."
                })

            # 2. Operating Cash Flow > 0
            cfo_cur = _find_item_val(cf, ["işletme faaliyet", "faaliyet nakit", "operating cash"], 0)
            if cfo_cur is not None:
                max_points += 1
                passed = cfo_cur > 0
                if passed:
                    score += 1
                signals.append({
                    "id": "cfo_positive",
                    "category": "Karlılık",
                    "title": "Faaliyet Nakit Akışı Pozitif",
                    "passed": bool(passed),
                    "detail": f"İşletme faaliyetlerinden nakit girişi sağlandı ({round(cfo_cur, 2)})" if passed else "Faaliyetlerden nakit çıkışı var."
                })

            # 3. Quality of earnings (CFO > Net Income)
            if net_inc_cur is not None and cfo_cur is not None:
                max_points += 1
                passed = cfo_cur > net_inc_cur
                if passed:
                    score += 1
                signals.append({
                    "id": "accrual_quality",
                    "category": "Nakit Kalitesi",
                    "title": "Nakit Kalitesi (CFO > Net Kâr)",
                    "passed": bool(passed),
                    "detail": "Kârın nakit karşılığı yüksek ve kaliteli" if passed else "Net kâr nakit akışından yüksek (muhasebesel tahakkuk payı var)"
                })

            # 4. Total Assets & ROA Trend
            assets_cur = _find_item_val(bs, ["toplam varlık", "toplam aktif"], 0)
            assets_prev = _find_item_val(bs, ["toplam varlık", "toplam aktif"], 1)
            net_inc_prev = _find_item_val(inc, ["dönem karı", "net kar", "net profit"], 1)
            if assets_cur and assets_prev and net_inc_cur is not None and net_inc_prev is not None:
                max_points += 1
                roa_cur = net_inc_cur / assets_cur if assets_cur else 0
                roa_prev = net_inc_prev / assets_prev if assets_prev else 0
                passed = roa_cur > roa_prev
                if passed:
                    score += 1
                signals.append({
                    "id": "roa_growth",
                    "category": "Verimlilik",
                    "title": "Aktif Karlılığı (ROA) Artışı",
                    "passed": bool(passed),
                    "detail": f"Aktif kârlılığı önceki döneme göre arttı (%{round(roa_cur*100, 2)} > %{round(roa_prev*100, 2)})" if passed else "Aktif kârlılığı geriledi."
                })

            # 5. Leverage (Long term debt)
            debt_cur = _find_item_val(bs, ["uzun vadeli yükümlülük", "uzun vadeli borç"], 0)
            debt_prev = _find_item_val(bs, ["uzun vadeli yükümlülük", "uzun vadeli borç"], 1)
            if debt_cur is not None and debt_prev is not None:
                max_points += 1
                passed = debt_cur <= debt_prev
                if passed:
                    score += 1
                signals.append({
                    "id": "lower_leverage",
                    "category": "Kaldıraç & Borç",
                    "title": "Uzun Vadeli Borç Eğilimi",
                    "passed": bool(passed),
                    "detail": "Uzun vadeli borç azaldı veya sabit kaldı" if passed else "Uzun vadeli borçlanma arttı"
                })

            # 6. Current Ratio (Likidite)
            ca_cur = _find_item_val(bs, ["dönen varlık"], 0)
            cl_cur = _find_item_val(bs, ["kısa vadeli yükümlülük"], 0)
            ca_prev = _find_item_val(bs, ["dönen varlık"], 1)
            cl_prev = _find_item_val(bs, ["kısa vadeli yükümlülük"], 1)
            if ca_cur and cl_cur and ca_prev and cl_prev:
                max_points += 1
                cr_cur = ca_cur / cl_cur if cl_cur else 0
                cr_prev = ca_prev / cl_prev if cl_prev else 0
                passed = cr_cur > cr_prev
                if passed:
                    score += 1
                signals.append({
                    "id": "higher_liquidity",
                    "category": "Likidite",
                    "title": "Cari Oran (Likidite) Artışı",
                    "passed": bool(passed),
                    "detail": f"Cari oran güçlendi ({round(cr_cur, 2)} > {round(cr_prev, 2)})" if passed else f"Cari oran geriledi ({round(cr_cur, 2)})"
                })

            # 7. Gross Margin trend
            rev_cur = _find_item_val(inc, ["satış gelir", "hasılat"], 0)
            gp_cur = _find_item_val(inc, ["brüt kar"], 0)
            rev_prev = _find_item_val(inc, ["satış gelir", "hasılat"], 1)
            gp_prev = _find_item_val(inc, ["brüt kar"], 1)
            if rev_cur and gp_cur and rev_prev and gp_prev:
                max_points += 1
                gm_cur = gp_cur / rev_cur if rev_cur else 0
                gm_prev = gp_prev / rev_prev if rev_prev else 0
                passed = gm_cur > gm_prev
                if passed:
                    score += 1
                signals.append({
                    "id": "higher_margin",
                    "category": "Operasyonel Verimlilik",
                    "title": "Brüt Kâr Marjı Artışı",
                    "passed": bool(passed),
                    "detail": f"Brüt marj iyileşti (%{round(gm_cur*100, 2)} > %{round(gm_prev*100, 2)})" if passed else f"Brüt marj daraldı (%{round(gm_cur*100, 2)})"
                })

            # Determine Rating
            ratio = (score / max_points) if max_points > 0 else 0
            if ratio >= 0.75:
                rating = "STRONG"
                rating_tr = "Güçlü Finansal Yapı"
            elif ratio >= 0.5:
                rating = "MODERATE"
                rating_tr = "Dengeli Finansal Yapı"
            else:
                rating = "WEAK"
                rating_tr = "Zayıf / Dikkat Edilmeli"

            return compact_payload({
                "symbol": symbol,
                "score": score,
                "max_score": max_points or 9,
                "rating": rating,
                "rating_tr": rating_tr,
                "valuation_multiples": {
                    "pe": clean_json_val(info.get("pe")),
                    "pddd": clean_json_val(info.get("pddd")),
                    "market_cap": clean_json_val(info.get("market_cap")),
                    "beta": clean_json_val(info.get("beta")),
                },
                "signals": signals
            })
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_static(f"HEALTH_{symbol}", fetch)


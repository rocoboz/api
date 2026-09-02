from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from api_core.services.analytics import analyze_sentiment
from api_core.services.cache import get_cached_market, get_cached_realtime
from api_core.services.normalizers import clean_json_val, df_to_json, normalize_fund_row, normalize_stock_row
from api_core.services.providers import FX, Fund, Index, Ticker, technical
from api_core.services.response import api_ok, pagination_meta
from api_core.services.security import limiter
from api_core.routes.funds import _list_funds_payload, list_funds
from api_core.routes.economy import get_economic_calendar
from api_core.routes.stocks import list_stocks

router = APIRouter(tags=["market"])


def _stock_screener_payload(template: str | None = None, limit: int = 100, offset: int = 0, sort: str | None = None, direction: str = "desc"):
    try:
        from tradingview_screener import Query as TvQuery

        q = TvQuery().set_markets("turkey").select("name", "close", "change", "volume", "price_book_ratio", "market_cap_basic", "price_earnings_ttm")
        _, df = q.get_scanner_data()
        if df.empty:
            return []
        df = df.rename(columns={"name": "symbol", "close": "price", "price_book_ratio": "pddd", "price_earnings_ttm": "pe", "market_cap_basic": "market_cap"})
        if sort and sort in df.columns:
            df = df.sort_values(sort, ascending=(direction == "asc"))
        sliced = df.iloc[offset : offset + limit]
        return [normalize_stock_row(row) for row in df_to_json(sliced)]
    except Exception as exc:
        return {"error": str(exc)}


def _market_heatmap_payload():
    try:
        from tradingview_screener import Query as TvQuery

        _, df = TvQuery().set_markets("turkey").select("name", "change", "volume", "sector").get_scanner_data()
        if df.empty:
            return []
        heatmap = []
        for _, row in df.head(50).iterrows():
            heatmap.append({"symbol": str(row.get("name")), "change": round(float(row.get("change", 0)), 2), "volume": float(row.get("volume", 0)), "sector": str(row.get("sector", "N/A"))})
        return heatmap
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/market/status")
@limiter.limit("60/minute")
def get_market_status(request: Request, response: Response):
    """Return Borsa Istanbul (BIST) current market session status, trading hours, and schedule."""
    from datetime import datetime, timezone, timedelta

    # Turkey Time is UTC+3
    tr_tz = timezone(timedelta(hours=3))
    now = datetime.now(tr_tz)
    weekday = now.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
    total_minutes = now.hour * 60 + now.minute

    # Schedule definitions (in minutes from midnight)
    t_pre_open = 9 * 60 + 40      # 09:40
    t_open_match = 9 * 60 + 55    # 09:55
    t_cont_start = 10 * 60        # 10:00
    t_close_order = 18 * 60       # 18:00
    t_close_match = 18 * 60 + 5   # 18:05
    t_close_trades = 18 * 60 + 8  # 18:08
    t_market_end = 18 * 60 + 10   # 18:10

    if weekday in (5, 6):
        is_open = False
        session = "WEEKEND"
        status_tr = "Hafta Sonu (Piyasa Kapalı)"
        next_session = "Pazartesi 09:40 (Açılış Seansı)"
    elif total_minutes < t_pre_open:
        is_open = False
        session = "PRE_MARKET"
        status_tr = "Seans Öncesi (Kapalı)"
        next_session = "09:40 (Açılış Seansı - Emir Toplama)"
    elif total_minutes < t_open_match:
        is_open = False
        session = "OPENING_AUCTION"
        status_tr = "Açılış Seansı (Emir Toplama)"
        next_session = "09:55 (Eşleştirme)"
    elif total_minutes < t_cont_start:
        is_open = False
        session = "OPENING_MATCH"
        status_tr = "Açılış Seansı (Eşleştirme)"
        next_session = "10:00 (Sürekli Müzayede Başlangıcı)"
    elif total_minutes < t_close_order:
        is_open = True
        session = "CONTINUOUS_AUCTION"
        status_tr = "Sürekli Müzayede (Seans Açık)"
        next_session = "18:00 (Kapanış Seansı - Emir Toplama)"
    elif total_minutes < t_close_match:
        is_open = False
        session = "CLOSING_AUCTION"
        status_tr = "Kapanış Seansı (Emir Toplama)"
        next_session = "18:05 (Kapanış Eşleştirme)"
    elif total_minutes < t_close_trades:
        is_open = False
        session = "CLOSING_MATCH"
        status_tr = "Kapanış Eşleştirme"
        next_session = "18:08 (Kapanış Fiyatlı İşlemler)"
    elif total_minutes < t_market_end:
        is_open = True
        session = "CLOSING_TRADES"
        status_tr = "Kapanış Fiyatlı İşlemler (Seans Açık)"
        next_session = "18:10 (Gün Sonu Kapanış)"
    else:
        is_open = False
        session = "CLOSED"
        status_tr = "Gün Sonu (Piyasa Kapalı)"
        next_session = "Yarın 09:40 (Açılış Seansı)" if weekday < 4 else "Pazartesi 09:40 (Açılış Seansı)"

    return {
        "exchange": "Borsa İstanbul (BIST)",
        "timezone": "Europe/Istanbul (UTC+3)",
        "server_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "is_open": is_open,
        "session": session,
        "status_description": status_tr,
        "next_event": next_session,
        "schedule": {
            "opening_auction": "09:40 - 09:55",
            "opening_match": "09:55 - 10:00",
            "continuous_trading": "10:00 - 18:00",
            "closing_auction": "18:00 - 18:05",
            "closing_match": "18:05 - 18:08",
            "closing_trades": "18:08 - 18:10",
        }
    }


@router.get("/market/overview")
@limiter.limit("60/minute")
def get_market_overview(request: Request, response: Response):
    """Return all-in-one market snapshot (BIST indices, currencies, gold, market status, and top movers)."""
    def fetch():
        from datetime import datetime, timezone, timedelta
        tr_tz = timezone(timedelta(hours=3))
        now = datetime.now(tr_tz)
        weekday = now.weekday()
        total_minutes = now.hour * 60 + now.minute
        is_open = (weekday < 5) and ((10 * 60 <= total_minutes < 18 * 60) or (18 * 60 + 8 <= total_minutes < 18 * 60 + 10))
        session_name = "WEEKEND" if weekday in (5, 6) else ("CONTINUOUS_AUCTION" if (10 * 60 <= total_minutes < 18 * 60) else "CLOSED")

        indices_data = {}
        for idx_sym in ["XU100", "XU030", "XBANK", "XUSIN"]:
            try:
                info = Index(idx_sym).info or {}
                indices_data[idx_sym] = {
                    "name": info.get("name", idx_sym),
                    "last": info.get("last"),
                    "change": info.get("change"),
                    "change_percent": info.get("change_percent")
                }
            except Exception:
                indices_data[idx_sym] = None

        fx_data = {}
        for fx_sym in ["USD", "EUR", "GBP"]:
            try:
                cur = FX(fx_sym).current or {}
                fx_data[fx_sym] = {
                    "rate": cur.get("last"),
                    "change_percent": cur.get("change_percent") or cur.get("change")
                }
            except Exception:
                fx_data[fx_sym] = None

        gold_data = {}
        try:
            gram = FX("gram-altin").current or {}
            gram_price = float(gram.get("last") or 0)
            gold_data["gram_altin"] = round(gram_price, 2)
            gold_data["ceyrek_altin"] = round(gram_price * 1.6065 * 1.04, 2) if gram_price > 0 else None
            gold_data["ons_altin_usd"] = float(FX("ons-altin-usd").current.get("last") or 0)
        except Exception:
            pass

        movers = {"gainers": [], "losers": []}
        try:
            from tradingview_screener import Query as TvQuery
            _, df = TvQuery().set_markets("turkey").select("name", "close", "change", "volume").get_scanner_data()
            if not df.empty:
                df = df.dropna(subset=["change", "close"])
                sorted_df = df.sort_values("change", ascending=False)
                movers["gainers"] = [
                    {"symbol": r["name"], "price": float(r["close"]), "change_percent": round(float(r["change"]), 2)}
                    for _, r in sorted_df.head(3).iterrows()
                ]
                movers["losers"] = [
                    {"symbol": r["name"], "price": float(r["close"]), "change_percent": round(float(r["change"]), 2)}
                    for _, r in sorted_df.tail(3).iloc[::-1].iterrows()
                ]
        except Exception:
            pass

        return {
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "market_status": {
                "is_open": is_open,
                "session": session_name,
                "timezone": "Europe/Istanbul (UTC+3)"
            },
            "indices": indices_data,
            "currencies": fx_data,
            "gold": gold_data,
            "movers": movers
        }

    return get_cached_realtime("MARKET_OVERVIEW_V3", fetch)


BIST_IPO_CALENDAR = [
    {
        "company_name": "Bahadır Kimya Sanayi ve Ticaret A.Ş.",
        "symbol": "BAHKM",
        "status": "COMPLETED",
        "offer_price": 51.0,
        "offer_dates": "05-06-07 Ağustos 2024",
        "lot_count": "16.000.000 Lot",
        "distribution_method": "Eşit Dağıtım",
        "lead_underwriter": "Tera Yatırım Menkul Değerler A.Ş.",
        "market": "BIST Ana Pazar",
        "trading_start_date": "13.08.2024"
    },
    {
        "company_name": "Horoz Lojistik Kargo Hizmetleri A.Ş.",
        "symbol": "HOROZ",
        "status": "COMPLETED",
        "offer_price": 55.0,
        "offer_dates": "29-30-31 Mayıs 2024",
        "lot_count": "24.600.000 Lot",
        "distribution_method": "Eşit Dağıtım",
        "lead_underwriter": "QNB Finans Yatırım",
        "market": "BIST Yıldız Pazar",
        "trading_start_date": "07.06.2024"
    },
    {
        "company_name": "Özata Denizcilik Sanayi ve Ticaret A.Ş.",
        "symbol": "OZATD",
        "status": "COMPLETED",
        "offer_price": 105.0,
        "offer_dates": "27-28-29 Ağustos 2024",
        "lot_count": "13.350.000 Lot",
        "distribution_method": "Eşit Dağıtım",
        "lead_underwriter": "Vakıf Yatırım Menkul Değerler A.Ş.",
        "market": "BIST Yıldız Pazar",
        "trading_start_date": "05.09.2024"
    },
    {
        "company_name": "Cem Zeytin A.Ş.",
        "symbol": "CEMZY",
        "status": "COMPLETED",
        "offer_price": 15.30,
        "offer_dates": "29-30 Ağustos - 02 Eylül 2024",
        "lot_count": "100.000.000 Lot",
        "distribution_method": "Eşit Dağıtım",
        "lead_underwriter": "Bulls Yatırım Menkul Değerler A.Ş.",
        "market": "BIST Yıldız Pazar",
        "trading_start_date": "09.09.2024"
    },
    {
        "company_name": "Durukan Şekerleme Sanayi ve Ticaret A.Ş.",
        "symbol": "DURKN",
        "status": "COMPLETED",
        "offer_price": 17.0,
        "offer_dates": "11-12 Eylül 2024",
        "lot_count": "42.500.000 Lot",
        "distribution_method": "Eşit Dağıtım",
        "lead_underwriter": "Deniz Yatırım Menkul Kıymetler A.Ş.",
        "market": "BIST Ana Pazar",
        "trading_start_date": "17.09.2024"
    },
    {
        "company_name": "Gündoğdu Gıda Süt Ürünleri San. ve Dış Tic. A.Ş.",
        "symbol": "GUNDG",
        "status": "COMPLETED",
        "offer_price": 35.0,
        "offer_dates": "15-16 Ağustos 2024",
        "lot_count": "10.000.000 Lot",
        "distribution_method": "Eşit Dağıtım",
        "lead_underwriter": "Alnus Yatırım Menkul Değerler A.Ş.",
        "market": "BIST Ana Pazar",
        "trading_start_date": "22.08.2024"
    },
    {
        "company_name": "Enda Enerji Holding A.Ş.",
        "symbol": "ENDA",
        "status": "UPCOMING",
        "offer_price": None,
        "offer_dates": "SPK Onayı Bekleniyor",
        "lot_count": "Belirlenmedi",
        "distribution_method": "Eşit Dağıtım",
        "lead_underwriter": "Tacirler Yatırım",
        "market": "BIST Yıldız Pazar",
        "trading_start_date": None
    },
    {
        "company_name": "Sümer Varlık Yönetim A.Ş.",
        "symbol": "SUMER",
        "status": "UPCOMING",
        "offer_price": None,
        "offer_dates": "Taslak İzahname Aşamasında",
        "lot_count": "Belirlenmedi",
        "distribution_method": "Eşit Dağıtım",
        "lead_underwriter": "Şeker Yatırım",
        "market": "BIST Ana Pazar",
        "trading_start_date": None
    }
]


@router.get("/market/ipo")
@limiter.limit("30/minute")
def get_ipo_calendar(request: Request, response: Response, status: str | None = None, envelope: bool = False):
    """Return Borsa Istanbul (BIST) Initial Public Offerings (IPO / Halka Arz) calendar."""
    ipos = BIST_IPO_CALENDAR
    if status and status.upper() in ("COMPLETED", "UPCOMING", "ACTIVE"):
        ipos = [item for item in ipos if item["status"] == status.upper()]

    active_count = sum(1 for x in BIST_IPO_CALENDAR if x["status"] == "ACTIVE")
    upcoming_count = sum(1 for x in BIST_IPO_CALENDAR if x["status"] == "UPCOMING")
    completed_count = sum(1 for x in BIST_IPO_CALENDAR if x["status"] == "COMPLETED")

    result = {
        "count": len(ipos),
        "total_tracked": len(BIST_IPO_CALENDAR),
        "active_count": active_count,
        "upcoming_count": upcoming_count,
        "completed_count": completed_count,
        "ipos": ipos
    }
    return api_ok(result) if envelope else result


@router.get("/market/screener")
@limiter.limit("20/minute")
def stock_screener(request: Request, response: Response, template: str | None = None, limit: int = 100, offset: int = 0, sort: str | None = None, direction: str = "desc", envelope: bool = False):
    def fetch():
        return _stock_screener_payload(template=template, limit=limit, offset=offset, sort=sort, direction=direction)

    payload = get_cached_market(f"SCREENER_V2_{template}_{limit}_{offset}_{sort}_{direction}", fetch)
    if isinstance(payload, dict) and payload.get("error"):
        return payload
    meta = pagination_meta(limit=limit, offset=offset, count=len(payload), sort=sort, direction=direction)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)
    response.headers["X-Count"] = str(len(payload))
    return api_ok(payload, meta) if envelope else payload


@router.get("/analysis/{symbol}")
@limiter.limit("20/minute")
def get_analysis_pro(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        obj = Fund(symbol) if len(symbol) == 3 else Ticker(symbol)
        df = obj.history(period="1y")
        if df.empty:
            return {"error": "No history"}
        rsi_s = technical.calculate_rsi(df)
        super_df = technical.calculate_supertrend(df)
        rsi = clean_json_val(rsi_s.iloc[-1])
        supertrend = clean_json_val(super_df["Supertrend"].iloc[-1]) if "Supertrend" in super_df else None
        ma50_v = df["Close"].rolling(50).mean()
        ma200_v = df["Close"].rolling(200).mean()
        ma50 = clean_json_val(ma50_v.iloc[-1]) if len(ma50_v) > 0 else None
        ma200 = clean_json_val(ma200_v.iloc[-1]) if len(ma200_v) > 0 else None
        current = float(df["Close"].iloc[-1])
        return {
            "symbol": symbol,
            "rsi": rsi,
            "supertrend": supertrend,
            "ma_comparison": {
                "ma50": ma50,
                "ma200": ma200,
                "trend": "BULLISH" if (ma50 is not None and ma200 is not None and ma50 > ma200) else "NEUTRAL",
                "price_vs_ma50": "ABOVE" if (ma50 is not None and current > ma50) else "BELOW",
            },
            "signal": "STRONG BUY" if (rsi is not None and rsi < 30 and ma200 is not None and current > ma200) else ("BUY" if (rsi is not None and rsi < 35) else ("SELL" if (rsi is not None and rsi > 70) else "NEUTRAL")),
        }

    return get_cached_market(f"ANALYSIS_PRO_V2_{symbol}", fetch)


@router.get("/analysis/{symbol}/indicators")
@limiter.limit("30/minute")
def get_technical_indicators(request: Request, response: Response, symbol: str):
    """Calculate and return comprehensive technical indicator values (RSI, MACD, Bollinger, EMAs, SMAs, ATR, Supertrend)."""
    symbol = symbol.upper()

    def fetch():
        try:
            tk = Ticker(symbol)
            df = tk.history(period="1y")
            if df.empty or len(df) < 30:
                return {"symbol": symbol, "error": "Insufficient historical data for technical calculation"}

            close = df["Close"]
            high = df["High"] if "High" in df else close
            low = df["Low"] if "Low" in df else close

            current_price = float(close.iloc[-1])

            # RSI 14
            rsi_series = technical.calculate_rsi(df, period=14)
            rsi_14 = round(float(rsi_series.iloc[-1]), 2) if not rsi_series.empty else None

            # MACD (12, 26, 9)
            macd_df = technical.calculate_macd(df, fast=12, slow=26, signal=9)
            if not macd_df.empty:
                macd_val = round(float(macd_df["MACD"].iloc[-1]), 3) if "MACD" in macd_df else None
                macd_sig = round(float(macd_df["Signal"].iloc[-1]), 3) if "Signal" in macd_df else None
                macd_hist = round(float(macd_df["Histogram"].iloc[-1]), 3) if "Histogram" in macd_df else None
            else:
                macd_val, macd_sig, macd_hist = None, None, None

            # Bollinger Bands (20, 2)
            try:
                bb_df = technical.calculate_bollinger_bands(df, period=20, std_dev=2.0)
                if not bb_df.empty:
                    bb_upper = round(float(bb_df["BB_Upper"].iloc[-1]), 2) if "BB_Upper" in bb_df else None
                    bb_middle = round(float(bb_df["BB_Middle"].iloc[-1]), 2) if "BB_Middle" in bb_df else None
                    bb_lower = round(float(bb_df["BB_Lower"].iloc[-1]), 2) if "BB_Lower" in bb_df else None
                    bandwidth = round(((bb_upper - bb_lower) / bb_middle * 100), 2) if (bb_upper and bb_lower and bb_middle) else None
                else:
                    bb_upper, bb_middle, bb_lower, bandwidth = None, None, None, None
            except Exception:
                bb_upper, bb_middle, bb_lower, bandwidth = None, None, None, None

            # Moving Averages
            sma_20 = round(float(close.rolling(20).mean().iloc[-1]), 2) if len(close) >= 20 else None
            sma_50 = round(float(close.rolling(50).mean().iloc[-1]), 2) if len(close) >= 50 else None
            sma_200 = round(float(close.rolling(200).mean().iloc[-1]), 2) if len(close) >= 200 else None

            ema_9 = round(float(close.ewm(span=9, adjust=False).mean().iloc[-1]), 2) if len(close) >= 9 else None
            ema_21 = round(float(close.ewm(span=21, adjust=False).mean().iloc[-1]), 2) if len(close) >= 21 else None
            ema_50 = round(float(close.ewm(span=50, adjust=False).mean().iloc[-1]), 2) if len(close) >= 50 else None

            # Supertrend
            st_df = technical.calculate_supertrend(df)
            if not st_df.empty and "Supertrend" in st_df:
                st_val = round(float(st_df["Supertrend"].iloc[-1]), 2)
                st_trend = "BULLISH" if current_price >= st_val else "BEARISH"
            else:
                st_val, st_trend = None, None

            # Signal interpretation
            rsi_cond = "OVERSOLD" if rsi_14 and rsi_14 < 30 else ("OVERBOUGHT" if rsi_14 and rsi_14 > 70 else "NEUTRAL")
            macd_cond = "BULLISH" if (macd_val and macd_sig and macd_val > macd_sig) else "BEARISH"

            # Overall Score (-100 to +100)
            score = 0
            if rsi_14:
                score += (30 - rsi_14) if rsi_14 < 30 else ((70 - rsi_14) if rsi_14 > 70 else 0)
            if macd_val and macd_sig:
                score += 25 if macd_val > macd_sig else -25
            if sma_50 and sma_200:
                score += 30 if sma_50 > sma_200 else -30
            if st_trend == "BULLISH":
                score += 20
            elif st_trend == "BEARISH":
                score -= 20

            overall = "STRONG_BUY" if score >= 45 else ("BUY" if score >= 15 else ("STRONG_SELL" if score <= -45 else ("SELL" if score <= -15 else "NEUTRAL")))

            return {
                "symbol": symbol,
                "current_price": current_price,
                "indicators": {
                    "rsi_14": rsi_14,
                    "macd": {
                        "macd": macd_val,
                        "signal": macd_sig,
                        "histogram": macd_hist
                    },
                    "bollinger": {
                        "upper": bb_upper,
                        "middle": bb_middle,
                        "lower": bb_lower,
                        "bandwidth_pct": bandwidth
                    },
                    "moving_averages": {
                        "sma_20": sma_20,
                        "sma_50": sma_50,
                        "sma_200": sma_200,
                        "ema_9": ema_9,
                        "ema_21": ema_21,
                        "ema_50": ema_50
                    },
                    "supertrend": {
                        "value": st_val,
                        "trend": st_trend
                    }
                },
                "summary": {
                    "rsi_condition": rsi_cond,
                    "macd_condition": macd_cond,
                    "trend_bias": overall
                }
            }
        except Exception as exc:
            return {"symbol": symbol, "error": str(exc)}

    return get_cached_market(f"INDICATORS_{symbol}", fetch)


@router.get("/analysis/{symbol}/insight")
@limiter.limit("10/minute")
def get_hybrid_insight(request: Request, response: Response, symbol: str):
    symbol = symbol.upper()

    def fetch():
        try:
            tk = Ticker(symbol)
            score = 50
            reasons: list[str] = []
            df = tk.history(period="1y")
            if not df.empty:
                rsi = technical.calculate_rsi(df).iloc[-1]
                if rsi < 30:
                    score += 15
                    reasons.append("RSI aşırı satım bölgesinde (Tepki yükselişi beklentisi)")
                elif rsi > 70:
                    score -= 15
                    reasons.append("RSI aşırı alım bölgesinde (Kar realizasyonu riski)")
                ma50 = df["Close"].rolling(50).mean().iloc[-1]
                ma200 = df["Close"].rolling(200).mean().iloc[-1]
                if ma50 > ma200:
                    score += 10
                    reasons.append("Golden Cross (50/200 MA) pozitif trend hakim")
            news_df = None
            try:
                news_df = tk.news
                if news_df is not None and not news_df.empty:
                    titles = news_df["Title"].head(15).tolist()
                    news_sent = analyze_sentiment(titles)
                    if news_sent["label"] == "BULLISH":
                        score += 15
                        reasons.append(f"Resmi KAP haber akışı pozitif ({news_sent['score']})")
                    elif news_sent["label"] == "BEARISH":
                        score -= 15
                        reasons.append(f"KAP haber akışında negatif başlıklar var ({news_sent['score']})")
            except Exception:
                pass
            pe = pddd = None
            try:
                from tradingview_screener import Query as TvQuery

                _, df_scr = TvQuery().set_markets("turkey").select("name", "price_earnings_ttm", "price_book_ratio").get_scanner_data()
                if not df_scr.empty:
                    match = df_scr[df_scr["name"] == symbol]
                    if not match.empty:
                        pe = match.iloc[0].get("price_earnings_ttm")
                        pddd = match.iloc[0].get("price_book_ratio")
                        if pe is not None and pe < 15:
                            score += 10
                            reasons.append(f"F/K oranı ({round(pe, 1)}) sektör ortalamasının altında")
                        if pddd is not None and pddd < 3:
                            score += 10
                            reasons.append(f"PD/DD ({round(pddd, 1)}) defter değerinde iskontolu")
            except Exception:
                pass
            final_score = max(0, min(100, score))
            sentiment = "VERY BULLISH" if final_score >= 80 else ("BULLISH" if final_score >= 60 else ("BEARISH" if final_score < 40 else "NEUTRAL"))
            return {
                "symbol": symbol,
                "score": final_score,
                "sentiment": sentiment,
                "reasons": reasons,
                "data_points": {
                    "rsi": round(rsi, 2) if "rsi" in locals() else None,
                    "pe": round(pe, 2) if pe is not None else None,
                    "pddd": round(pddd, 2) if pddd is not None else None,
                    "news_count": len(news_df) if news_df is not None else 0,
                },
            }
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"INSIGHT_{symbol}", fetch)


@router.get("/market/breadth")
@limiter.limit("5/minute")
def get_market_breadth(request: Request, response: Response):
    def fetch():
        try:
            from tradingview_screener import Query as TvQuery

            _, df = TvQuery().set_markets("turkey").select("name", "change", "volume", "sector").get_scanner_data()
            if df.empty:
                return {"error": "Breadth data unavailable"}
            changes = df["change"].astype(float)
            up = int((changes > 0).sum())
            down = int((changes < 0).sum())
            neutral = int((changes == 0).sum())
            up_volume = float(df.loc[changes > 0, "volume"].sum())
            down_volume = float(df.loc[changes < 0, "volume"].sum())
            return {"up": up, "down": down, "neutral": neutral, "up_volume": up_volume, "down_volume": down_volume, "ratio": round(up / down, 2) if down > 0 else up, "sentiment": "BULLISH" if up > down * 1.5 else ("BEARISH" if down > up * 1.5 else "NEUTRAL")}
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_realtime("MARKET_BREADTH", fetch)


@router.get("/market/heatmap")
@limiter.limit("15/minute")
def get_market_heatmap(request: Request, response: Response):
    def fetch():
        return _market_heatmap_payload()

    return get_cached_market("MARKET_HEATMAP", fetch)


@router.get("/market/summary")
@limiter.limit("20/minute")
def market_summary(request: Request, response: Response):
    def fetch():
        try:
            from tradingview_screener import Query as TvQuery

            _, breadth_df = TvQuery().set_markets("turkey").select("name", "change", "volume", "sector").get_scanner_data()
            if breadth_df.empty:
                breadth = {"up": 0, "down": 0, "neutral": 0, "ratio": 0, "sentiment": "NEUTRAL"}
            else:
                changes = breadth_df["change"].astype(float)
                up = int((changes > 0).sum())
                down = int((changes < 0).sum())
                neutral = int((changes == 0).sum())
                breadth = {"up": up, "down": down, "neutral": neutral, "ratio": round(up / down, 2) if down > 0 else up, "sentiment": "BULLISH" if up > down * 1.5 else ("BEARISH" if down > up * 1.5 else "NEUTRAL")}
        except Exception:
            breadth = {"up": 0, "down": 0, "neutral": 0, "ratio": 0, "sentiment": "NEUTRAL"}
        heatmap = _market_heatmap_payload()
        movers = _stock_screener_payload(limit=6, offset=0)
        funds = _list_funds_payload(limit=6, offset=0)
        calendar = get_economic_calendar(scope="week")
        return api_ok({"breadth": breadth if isinstance(breadth, dict) else {}, "heatmap": heatmap if isinstance(heatmap, list) else [], "movers": movers if isinstance(movers, list) else [], "funds": funds if isinstance(funds, list) else [], "calendar": calendar[:6] if isinstance(calendar, list) else []})

    return get_cached_market("MARKET_SUMMARY", fetch)


@router.get("/home/highlights")
@limiter.limit("20/minute")
def home_highlights(request: Request, response: Response):
    def fetch():
        movers = _stock_screener_payload(limit=4, offset=0)
        funds = _list_funds_payload(limit=4, offset=0)
        return api_ok({"stocks": movers if isinstance(movers, list) else [], "funds": funds if isinstance(funds, list) else []})

    return get_cached_market("HOME_HIGHLIGHTS", fetch)


@router.get("/market/scan")
@limiter.limit("10/minute")
def scan_market(
    request: Request,
    response: Response,
    universe: str = Query("XU030", description="Index code (e.g. XU100, XU030) or comma-separated symbols"),
    condition: str = Query(..., description="Scan condition (e.g. 'rsi < 30', 'close > sma_50')"),
    interval: str = Query("1d", description="Granularity ('1m', '5m', '15m', '30m', '1h', '4h', '1d', '1W', '1M')"),
    limit: int = Query(100, description="Max result count")
):
    def fetch():
        try:
            from finans_core import scan
            univ = [s.strip().upper() for s in universe.split(",")] if "," in universe else universe.upper()
            df = scan(universe=univ, condition=condition, interval=interval, limit=limit)
            if df.empty:
                return []
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_realtime(f"SCAN_{universe}_{condition}_{interval}_{limit}", fetch)


def _fetch_rss(url: str, source_name: str, max_items: int = 10):
    import urllib.request
    import xml.etree.ElementTree as ET
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        items = []
        for item in root.findall(".//item")[:max_items]:
            title = item.find("title")
            link = item.find("link")
            pub_date = item.find("pubDate") or item.find("date")
            desc = item.find("description")
            items.append({
                "source": source_name,
                "title": title.text.strip() if title is not None and title.text else "",
                "link": link.text.strip() if link is not None and link.text else "",
                "date": pub_date.text.strip() if pub_date is not None and pub_date.text else "",
                "summary": desc.text.strip() if desc is not None and desc.text else ""
            })
        return items
    except Exception:
        return []


@router.get("/market/news")
@limiter.limit("10/minute")
def get_market_news(request: Request, response: Response, local: bool = True, global_news: bool = True):
    def fetch():
        news_items = []
        if local:
            news_items.extend(_fetch_rss("https://www.bloomberght.com/rss", "Bloomberg HT", 10))
        if global_news:
            news_items.extend(_fetch_rss("https://www.cnbc.com/id/10000664/device/rss/rss.html", "CNBC Finance", 10))
        return news_items

    return get_cached_realtime(f"NEWS_{local}_{global_news}", fetch)


SCAN_PRESETS = {
    "golden-cross": {
        "title": "Golden Cross (Altın Kesişme)",
        "description": "50 günlük hareketli ortalamanın 200 günlük ortalamayı yukarı kırdığı yükseliş sinyali",
        "condition": "sma_50 > sma_200",
        "default_universe": "XU100",
    },
    "oversold": {
        "title": "Aşırı Satım Bölgesi (RSI < 30)",
        "description": "14 günlük RSI değeri 30 seviyesinin altına inmiş, dip ve tepki arayışındaki hisseler",
        "condition": "rsi < 30",
        "default_universe": "XU100",
    },
    "overbought": {
        "title": "Aşırı Alım Bölgesi (RSI > 70)",
        "description": "RSI değeri 70 üzerine çıkmış, güçlü ivmede seyreden veya kâr satışı riski olan hisseler",
        "condition": "rsi > 70",
        "default_universe": "XU100",
    },
    "macd-bullish": {
        "title": "MACD Al Sinyali",
        "description": "MACD çizgisi sinyal çizgisini yukarı yönlü kesen pozitif momentum hisseleri",
        "condition": "macd > macd_signal",
        "default_universe": "XU100",
    },
    "supertrend-bullish": {
        "title": "Supertrend Yükseliş Trendi",
        "description": "Supertrend göstergesi 'Al' sinyalinde olan ve trendini koruyan hisseler",
        "condition": "supertrend_direction == 1",
        "default_universe": "XU030",
    },
    "bollinger-breakout": {
        "title": "Bollinger Üst Bant Kırılımı",
        "description": "Kapanış fiyatı Bollinger üst bandını test eden veya yukarı zorlayan hisseler",
        "condition": "close > bbands_upper",
        "default_universe": "XU100",
    },
}


@router.get("/market/presets")
@limiter.limit("20/minute")
def list_presets(request: Request, response: Response):
    """List all available pre-configured technical scan presets."""
    items = []
    for key, meta in SCAN_PRESETS.items():
        items.append({
            "key": key,
            "title": meta["title"],
            "description": meta["description"],
            "condition": meta["condition"],
            "default_universe": meta["default_universe"],
        })
    return items


@router.get("/market/presets/{preset_name}")
@limiter.limit("10/minute")
def run_preset(
    request: Request,
    response: Response,
    preset_name: str,
    universe: str | None = None,
    interval: str = "1d",
    limit: int = 50,
):
    """Run a pre-configured technical scan preset."""
    preset = SCAN_PRESETS.get(preset_name.lower())
    if not preset:
        return {"error": f"Unknown preset '{preset_name}'. Valid presets: {list(SCAN_PRESETS.keys())}"}

    target_universe = (universe or preset["default_universe"]).upper()
    condition = preset["condition"]

    def fetch():
        try:
            from finans_core import scan
            univ = [s.strip().upper() for s in target_universe.split(",")] if "," in target_universe else target_universe
            df = scan(universe=univ, condition=condition, interval=interval, limit=limit)
            results = [] if df.empty else df_to_json(df)
            return {
                "preset": preset_name,
                "title": preset["title"],
                "description": preset["description"],
                "condition": condition,
                "universe": target_universe,
                "count": len(results),
                "data": results,
            }
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_realtime(f"PRESET_{preset_name}_{target_universe}_{interval}_{limit}", fetch)




from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from api_core.services.analytics import analyze_sentiment
from api_core.services.cache import get_cached_market, get_cached_realtime
from api_core.services.normalizers import clean_json_val, df_to_json, normalize_fund_row, normalize_stock_row
from api_core.services.providers import Fund, Ticker, technical
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


@router.get("/analysis/{symbol}/sentiment")
@limiter.limit("10/minute")
def get_sentiment_analysis(request: Request, response: Response, symbol: str):
    def fetch():
        try:
            import os

            env_token = os.getenv("TWITTER_AUTH_TOKEN")
            env_ct0 = os.getenv("TWITTER_CT0")
            if env_token and env_ct0:
                from api_core.services.providers import set_twitter_auth, search_tweets

                set_twitter_auth(auth_token=env_token, ct0=env_ct0)
                tweets_df = search_tweets(symbol, limit=15)
                if tweets_df.empty:
                    return {"error": "No tweets found for sentiment"}
                return {"symbol": symbol, "sentiment": analyze_sentiment(tweets_df["text"].tolist())}
            return {"error": "Twitter Auth missing for sentiment engine"}
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"SENTIMENT_{symbol}", fetch)


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




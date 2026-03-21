from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from api_core.services.analytics import analyze_sentiment
from api_core.services.cache import get_cached_market, get_cached_realtime
from api_core.services.normalizers import clean_json_val, df_to_json, normalize_fund_row, normalize_stock_row
from api_core.services.providers import Fund, Ticker, technical
from api_core.services.response import api_ok, pagination_meta
from api_core.services.security import limiter
from api_core.routes.funds import list_funds
from api_core.routes.economy import get_economic_calendar
from api_core.routes.stocks import list_stocks

router = APIRouter(tags=["market"])


@router.get("/market/screener")
def stock_screener(response: Response, template: str | None = None, limit: int = 100, offset: int = 0, sort: str | None = None, direction: str = "desc", envelope: bool = False):
    def fetch():
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

    payload = get_cached_market(f"SCREENER_V2_{template}_{limit}_{offset}_{sort}_{direction}", fetch)
    if isinstance(payload, dict) and payload.get("error"):
        return payload
    meta = pagination_meta(limit=limit, offset=offset, count=len(payload), sort=sort, direction=direction)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)
    response.headers["X-Count"] = str(len(payload))
    return api_ok(payload, meta) if envelope else payload


@router.get("/analysis/{symbol}")
def get_analysis_pro(symbol: str):
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
def get_sentiment_analysis(symbol: str):
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
def get_hybrid_insight(symbol: str):
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
def get_market_breadth(request: Request):
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
def get_market_heatmap():
    def fetch():
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

    return get_cached_market("MARKET_HEATMAP", fetch)


@router.get("/market/summary")
def market_summary():
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
        heatmap = get_market_heatmap()
        movers = stock_screener(Response(), limit=6, offset=0)
        funds = list_funds(Response(), limit=6, offset=0)
        calendar = get_economic_calendar(scope="week")
        return api_ok({"breadth": breadth if isinstance(breadth, dict) else {}, "heatmap": heatmap if isinstance(heatmap, list) else [], "movers": movers if isinstance(movers, list) else [], "funds": funds if isinstance(funds, list) else [], "calendar": calendar[:6] if isinstance(calendar, list) else []})

    return get_cached_market("MARKET_SUMMARY", fetch)


@router.get("/home/highlights")
def home_highlights():
    def fetch():
        movers = stock_screener(Response(), limit=4, offset=0)
        funds = list_funds(Response(), limit=4, offset=0)
        return api_ok({"stocks": movers if isinstance(movers, list) else [], "funds": funds if isinstance(funds, list) else []})

    return get_cached_market("HOME_HIGHLIGHTS", fetch)

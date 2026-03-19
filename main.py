import os
import sys
import json
import asyncio
import httpx
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from zoneinfo import ZoneInfo

import threading
from concurrent.futures import ThreadPoolExecutor
base_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(base_dir, 'borsapy_lib')
if os.path.exists(lib_path):
    # Use append instead of insert(0) to prioritize pip-installed Linux packages on Render
    # while still allowing custom 'borsapy' library to be found.
    sys.path.append(lib_path)

# --- THIRD PARTY ---
from fastapi import FastAPI, HTTPException, Query, Request, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from cachetools import TTLCache

# --- BORSAPY IMPORTS ---
import re
try:
    import fitz # PyMuPDF
except ImportError:
    fitz = None

try:
    from borsapy import Ticker, FX, Crypto, Fund, Index, Bond, Eurobond
    from borsapy import market, technical, screener, EconomicCalendar
    from borsapy import Inflation, TCMB, VIOP, Portfolio, tax
    from borsapy import search_funds, screen_funds, compare_funds
    from borsapy import search_tweets, set_twitter_auth, clear_twitter_auth
    from borsapy.twitter import search_tweets
    from borsapy._providers.kap import get_kap_provider
    from borsapy._providers.kap_holdings import get_kap_holdings_provider
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    pass

# --- DEEP HOLDINGS PARSER (No-LLM Mode) ---
def parse_fund_holdings_no_llm(fund_code: str):
    """
    Scrapes KAP for the latest PDR PDF and extracts symbols/weights using Regex (v1.0.7).
    """
    fund_code = fund_code.upper()
    try:
        # 1. Get Fund OID from KAP
        tefas = Fund(fund_code)
        kap_url = tefas.info.get("kap_link")
        if not kap_url: return None
        
        # Extract potential OIDs from KAP page
        resp = httpx.get(kap_url, timeout=10)
        oids = re.findall(r'([a-fA-F0-9]{32})', resp.text)
        if not oids: return None
        
        # 2. Find latest PDR disclosure
        # Disclosure type for PDR: 8aca490d502e34b801502e380044002b
        pdr_type = "8aca490d502e34b801502e380044002b"
        disclosures = None
        
        # Try finding the correct OID that actually returns PDRs
        print(f"DEBUG: Found {len(set(oids))} potential OIDs for {fund_code}")
        for fund_oid in set(oids):
            try:
                filter_url = f"https://kap.org.tr/tr/api/disclosure/filter/FILTERYFBF/{fund_oid}/{pdr_type}/365"
                f_resp = httpx.get(filter_url, timeout=5)
                if f_resp.status_code == 200:
                    data = f_resp.json()
                    if data:
                        print(f"DEBUG: Found valid OID: {fund_oid}")
                        disclosures = data
                        break
            except: continue
            
        if not disclosures: 
            print(f"DEBUG: No PDR disclosures found for {fund_code}")
            return None
        
        latest_idx = disclosures[0]["disclosureBasic"]["disclosureIndex"]
        print(f"DEBUG: Latest PDR Index: {latest_idx}")
        
        # 3. Get Attachment File ID
        disc_page = f"https://www.kap.org.tr/tr/Bildirim/{latest_idx}"
        resp = httpx.get(disc_page, timeout=10)
        file_id_match = re.search(r'file/download/([a-f0-9]{32})', resp.text)
        if not file_id_match: 
            print(f"DEBUG: File ID not found in disclosure {latest_idx}")
            return None
        file_id = file_id_match.group(1)
        
        # 4. Download and Parse PDF
        print(f"DEBUG: Downloading PDF {file_id}")
        pdf_url = f"https://kap.org.tr/tr/api/file/download/{file_id}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        resp = httpx.get(pdf_url, headers=headers, timeout=30)
        data = resp.content
        pdf_start = data.find(b"%PDF-")
        if pdf_start == -1: 
            print(f"DEBUG: Valid PDF header not found for {fund_code}")
            return None
        
        pdf_data = data[pdf_start:]
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        for page in doc: text += page.get_text()
        print(f"DEBUG: PDF text extracted, length: {len(text)}")
        
        # 5. Extract Stocks & Weights
        print(f"DEBUG: Starting Regex scan for holdings...")
        unique_stocks = {}
        
        from borsapy import market
        try:
            bist_tickers = set(market.companies()['ticker'].tolist())
        except:
            bist_tickers = set()
            
        for match in re.finditer(r'\n([A-Z]{4,5})\s*\n', text):
            sym = match.group(1)
            if not bist_tickers or sym not in bist_tickers: continue
            
            sym_pos = match.end()
            search_window = text[sym_pos:sym_pos+300]
            
            # Robust KAP PDR table matcher
            weight_match = re.search(r'(\d+,\d{2})\s*\n\s*(\d+,\d{2})\s*\n\s*(?:TL|TRY|USD|EUR)', search_window)
            if weight_match:
                val = weight_match.group(2) # FTD (Fund Total Value - Net Asset Weight) avoids >100%
            else:
                # Fallback: check all numbers, skip huge values (like share counts), get a realistic %
                nums = re.findall(r'(\d+,\d{2})', search_window)
                val = next((n for n in reversed(nums) if 0.01 <= float(n.replace(',', '.')) <= 40.0), None)
                
            if val:
                try:
                    weight = float(val.replace(',', '.'))
                    if 0.05 <= weight <= 40:
                        unique_stocks[sym] = max(unique_stocks.get(sym, 0), weight)
                except: continue
        
        return [{"symbol": s, "weight": w} for s, w in unique_stocks.items()]
    except Exception as e:
        print(f"Deep Parsing Error for {fund_code}: {e}")
        return None

# --- SECURITY & CONFIG ---
API_KEY = os.getenv("API_KEY", "CHANGE_ME") # Set via Render environment
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if API_KEY == "OPEN": return True
    if api_key and api_key == API_KEY: return True
    raise HTTPException(status_code=403, detail="Invalid or Missing API Key")

# --- APP SETUP ---
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="BorsaPy Ultimate API",
    description="Professional Financial Gateway for Turkish Markets. (v1.0.7 - Performance)",
    version="1.0.7"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CACHING SYSTEM (v1.0.7 Optimized & Ban-Proof) ---
REALTIME_CACHE = TTLCache(maxsize=500, ttl=30) # Price, Depth (30s - Safer for Ban Protection)
MARKET_CACHE = TTLCache(maxsize=200, ttl=60) # Screener, VIOP (60s)
STATIC_CACHE = TTLCache(maxsize=1000, ttl=86400) # Info, Tax, Inflation, KAP (24h)

def get_cached_realtime(key: str, func):
    if key in REALTIME_CACHE: return REALTIME_CACHE[key]
    data = func()
    REALTIME_CACHE[key] = data
    return data

def get_cached_market(key: str, func):
    if key in MARKET_CACHE: return MARKET_CACHE[key]
    data = func()
    MARKET_CACHE[key] = data
    return data

def get_cached_static(key: str, func):
    if key in STATIC_CACHE: return STATIC_CACHE[key]
    data = func()
    STATIC_CACHE[key] = data
    return data

# --- UTILS ---
def df_to_json(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df is None or (hasattr(df, 'empty') and df.empty): return []
    # Clean Info for JSON safely using pandas' built-in to_json which handles NaNs as nulls
    return json.loads(df.to_json(orient="records", date_format="iso"))

# --- LIGHTWEIGHT SENTIMENT ENGINE (v1.1.0) ---
FINANCIAL_KEYWORDS = {
    "positive": ["tavan", "yükseliş", "alım", "rekor", "kar", "büyüme", "temettü", "pozitif", "destek", "hedef", "bullish", "buy", "profit", "growth", "dividend"],
    "negative": ["taban", "düşüş", "satış", "zarar", "negatif", "direnç", "risk", "ayı", "bearish", "sell", "loss", "risk", "warning", "crash"]
}

def analyze_sentiment(text_list: List[str]) -> Dict[str, Any]:
    if not text_list: return {"score": 0, "label": "NEUTRAL", "confidence": 0}
    
    total_score = 0
    mentions = 0
    for text in text_list:
        text = text.lower()
        pos = sum(1 for word in FINANCIAL_KEYWORDS["positive"] if word in text)
        neg = sum(1 for word in FINANCIAL_KEYWORDS["negative"] if word in text)
        total_score += (pos - neg)
        mentions += (pos + neg)
    
    score = round(total_score / len(text_list), 2) if text_list else 0
    label = "BULLISH" if score > 0.1 else ("BEARISH" if score < -0.1 else "NEUTRAL")
    
    return {
        "score": score,
                "label": label,
        "mentions_detected": mentions,
        "sample_count": len(text_list)
    }

# --- STARTUP ---
@app.on_event("startup")
async def startup_event():
    # Keep-Alive Self-Ping
    async def ping_regularly():
        url = os.getenv("RENDER_EXTERNAL_URL")
        if not url: return
        while True:
            await asyncio.sleep(14 * 60)
            try:
                async with httpx.AsyncClient() as client:
                    await client.get(f"{url}/ping", timeout=5.0)
            except: pass
    asyncio.create_task(ping_regularly())
    
    # Twitter Auth
    T_TOKEN = os.getenv("TWITTER_AUTH_TOKEN")
    T_CT0 = os.getenv("TWITTER_CT0")
    if T_TOKEN and T_CT0:
        try:
            from borsapy import set_twitter_auth
            set_twitter_auth(auth_token=T_TOKEN, ct0=T_CT0)
        except: pass

# --- GLOBAL LOCKS ---
twitter_lock = threading.Lock()

# --- ENDPOINTS: BASE ---
@app.get("/ping")
def ping(): return {"status": "ok", "time": datetime.now().isoformat()}

@app.get("/")
def home():
    return {
        "service": "BorsaPy Ultimate API",
        "version": "1.0.7",
        "github": "https://github.com/rocoboz/api",
        "docs": "/docs"
    }

# --- ENDPOINTS: STOCKS ---
@app.get("/stocks/list")
def list_stocks():
    return get_cached_static("STOCKS_LIST", lambda: df_to_json(market.companies()))

@app.get("/stocks/{symbol}")
def get_stock(symbol: str):
    symbol = symbol.upper()
    def fetch():
        tk = Ticker(symbol)
        # Convert FastInfo to regular dict for item assignment
        try:
            info = dict(tk.fast_info) if hasattr(tk, 'fast_info') else dict(tk.info)
        except:
            info = dict(tk.info)
            
        # Add KAP Details (CACHED STATICALLY FOR 24H)
        def fetch_kap():
            try:
                kap = get_kap_provider()
                return kap.get_company_details(symbol)
            except: return {}
            
        info['details'] = get_cached_static(f"KAP_DETAILS_{symbol}", fetch_kap)
        return {"symbol": symbol, "data": info}
    return get_cached_market(f"STOCK_{symbol}", fetch)

@app.get("/stocks/{symbol}/history")
def stock_history(symbol: str, period: str = "1mo", interval: str = "1d"):
    key = f"HIST_{symbol}_{period}_{interval}"
    def fetch():
        tk = Ticker(symbol)
        return df_to_json(tk.history(period=period, interval=interval))
    return get_cached_market(key, fetch)

@app.get("/stocks/{symbol}/depth")
@limiter.limit("10/minute")
def get_simulated_depth(request: Request, symbol: str):
    """
    Simulates Order Flow / Depth using Volume-at-Price analysis (v1.0.7).
    """
    symbol = symbol.upper()
    def fetch():
        tk = Ticker(symbol)
        # Fetch 1 day of 5m data
        hist = tk.history(period="1d", interval="5m")
        if hist.empty: return {"error": "Insufficient intraday data"}
        
        # Group volume by price bins
        # We'll create roughly 20 bins across the daily range
        low, high = hist["Low"].min(), hist["High"].max()
        if high == low: high += 0.01
        
        bins = np.linspace(low, high, 20)
        hist["PriceBin"] = pd.cut(hist["Close"], bins=bins, labels=bins[:-1])
        
        # Calculate Volume Profile
        vp = hist.groupby("PriceBin")["Volume"].sum().reset_index()
        vp = vp.dropna().sort_values("PriceBin", ascending=False)
        
        result = []
        total_vol = vp["Volume"].sum()
        for _, row in vp.iterrows():
            result.append({
                "price": round(float(row["PriceBin"]), 2),
                "volume": int(row["Volume"]),
                "weight": round((row["Volume"] / total_vol) * 100, 1)
            })
        return {"symbol": symbol, "simulated_depth": result, "method": "Volume-at-Price Profile"}
    return get_cached_realtime(f"DEPTH_{symbol}", fetch)

@app.get("/stocks/{symbol}/disclosures")
def get_disclosures(symbol: str, limit: int = 15):
    def fetch():
        kap = get_kap_provider()
        return df_to_json(kap.get_disclosures(symbol, limit))
    return get_cached_market(f"DISC_{symbol}_{limit}", fetch)

@app.get("/stocks/compare")
def compare(symbols: str = Query(...)):
    sym_list = [s.strip().upper() for s in symbols.split(",")]
    def fetch():
        res = []
        for s in sym_list:
            tk = Ticker(s)
            res.append({"symbol": s, "price": tk.info.get("last_price"), "pe": tk.info.get("pe")})
        return res
    return get_cached_market(f"COMPARE_{symbols}", fetch)

@app.get("/market/screener")
def stock_screener(template: Optional[str] = None):
    """
    Returns high-performance stock screening data using TradingView (v1.0.7).
    """
    def fetch():
        try:
            from tradingview_screener import Query
            # Fetching: Name, Close, Change, Volume, P/E (TTM), P/B (Ratio), Market Cap
            q = Query().set_markets('turkey').select(
                'name', 'close', 'change', 'volume', 'price_book_ratio', 'market_cap_basic', 'price_earnings_ttm'
            )
            _, df = q.get_scanner_data()
            
            if df.empty: return []
            
            # Map columns to user-friendly names
            df = df.rename(columns={
                "name": "symbol",
                "close": "price",
                "price_book_ratio": "pddd",
                "price_earnings_ttm": "pe",
                "market_cap_basic": "market_cap"
            })
            
            # Clean values (nan -> null)
            return df_to_json(df)
        except Exception as e:
            return {"error": str(e)}
    return get_cached_market(f"SCREENER_V2_{template}", fetch)

@app.get("/stocks/{symbol}/dividends")
def get_dividends(symbol: str):
    symbol = symbol.upper()
    def fetch():
        try:
            tk = Ticker(symbol)
            divs = tk.dividends
            if divs is None or divs.empty: return []
            # Normalize column names for JSON
            df = divs.reset_index()
            df = df.rename(columns={"Date": "date", "Amount": "amount", "GrossRate": "gross", "NetRate": "net"})
            return df_to_json(df)
        except Exception:
            return [] # Fail gracefully if provider has data issues
    return get_cached_static(f"DIVS_{symbol}", fetch)

@app.get("/stocks/{symbol}/financials")
def get_financials(symbol: str, type: str = "income"):
    """
    Returns financial statements: 'income', 'balance', 'cash' (v1.1.0).
    """
    symbol = symbol.upper()
    def fetch():
        try:
            tk = Ticker(symbol)
            if type == "balance": df = tk.balance_sheet
            elif type == "cash": df = tk.cash_flow
            else: df = tk.income_stmt
            
            if df is None or df.empty: return {"error": "No data"}
            # Financials are complex, simplify
            return json.loads(df.to_json(date_format="iso"))
        except Exception:
            return {"error": "Financial data currently unavailable"}
    return get_cached_static(f"FIN_{symbol}_{type}", fetch)

@app.get("/analysis/{symbol}")
def get_analysis_pro(symbol: str):
    symbol = symbol.upper()
    def fetch():
        tk = Ticker(symbol)
        df = tk.history(period="1y")
        if df.empty: return {"error": "No history"}
        rsi = technical.calculate_rsi(df).iloc[-1]
        supertrend = technical.calculate_supertrend(df).iloc[-1]
        
        # Add simpler signals
        ma50 = df['Close'].rolling(50).mean().iloc[-1]
        ma200 = df['Close'].rolling(200).mean().iloc[-1]
        current = df['Close'].iloc[-1]
        
        return {
            "symbol": symbol,
            "rsi": round(rsi, 2) if not np.isnan(rsi) else None,
            "supertrend": round(supertrend["Supertrend"], 2) if "Supertrend" in supertrend else None,
            "ma_comparison": {
                "ma50": round(ma50, 2),
                "ma200": round(ma200, 2),
                "trend": "BULLISH" if ma50 > ma200 else "BEARISH",
                "price_vs_ma50": "ABOVE" if current > ma50 else "BELOW"
            },
            "signal": "STRONG BUY" if rsi < 30 and current > ma200 else ("BUY" if rsi < 35 else ("SELL" if rsi > 70 else "NEUTRAL"))
        }
    return get_cached_market(f"ANALYSIS_PRO_{symbol}", fetch)

@app.get("/analysis/{symbol}/sentiment")
def get_sentiment_analysis(symbol: str):
    """
    Scrapes Twitter/X for the symbol and applies AI Sentiment scoring (v1.1.0).
    """
    def fetch():
        try:
            # Re-use existing search logic internally
            with twitter_lock:
                env_token = os.getenv("TWITTER_AUTH_TOKEN")
                env_ct0 = os.getenv("TWITTER_CT0")
                if env_token and env_ct0:
                    set_twitter_auth(auth_token=env_token, ct0=env_ct0)
                    tweets_df = search_tweets(symbol, limit=15)
                    if tweets_df.empty: return {"error": "No tweets found for sentiment"}
                    
                    texts = tweets_df['text'].tolist()
                    analysis = analyze_sentiment(texts)
                    return {"symbol": symbol, "sentiment": analysis}
                return {"error": "Twitter Auth missing for sentiment engine"}
        except Exception as e:
            return {"error": str(e)}
    return get_cached_market(f"SENTIMENT_{symbol}", fetch)

# --- ENDPOINTS: FUNDS ---

@app.get("/funds/{code}/estimated-return")
@limiter.limit("10/minute")
def get_fund_estimated_return(request: Request, code: str):
    """
    Calculates the real-time daily return estimate of a fund by deep-scanning its PDR PDF (v1.0.7).
    """
    code = code.upper()
    def fetch():
        f = Fund(code)
        info = f.info
        
        # 1. Parsing holdings (CACHED STATICALLY FOR 24H TO PREVENT KAP BANS)
        holdings = get_cached_static(f"HOLDINGS_SCAN_{code}", lambda: parse_fund_holdings_no_llm(code))
        
        # 2. Daily benchmark reference
        try:
            bist = Index("XU100").info.get("change_percent", 0) / 100
        except: bist = 0
        
        daily_fixed = 0.0012 # 0.12% daily proxy for cash/repo/fixed
        estimate = 0.0
        details = []
        mode = ""
      # Determine total TEFAS Hisse Senedi weight
        alloc = info.get("allocation", [])
        tefas_hisse_weight = sum((a.get("weight", 0)/100) for a in alloc if any(x in a.get("asset_name", "").lower() for x in ["hisse senedi", "stock", "equity"]))
        
        # If we have specific holdings, use them for the "Hisse Senedi" portion
        if holdings:
            stocks_total_weight = 0
            stocks_calculated_return = 0
            
            # Fetch all stock returns in 1 second using Screener
            changes = {}
            try:
                from tradingview_screener import Query
                _, df = Query().set_markets('turkey').select('name', 'change').get_scanner_data()
                if not df.empty:
                    changes = dict(zip(df['name'], df['change'].astype(float)))
            except: pass
            
            for h in holdings:
                sym = h['symbol']
                weight = h['weight'] / 100
                
                # change is already a percentage like 5.5 for %5.5, thus divide by 100
                s_ret = changes.get(sym, bist * 100) / 100
                contribution = weight * s_ret
                stocks_calculated_return += contribution
                stocks_total_weight += weight
                
                details.append({
                    "asset": sym, 
                    "weight": round(weight*100, 2), 
                    "daily_return": round(s_ret*100, 2),
                    "impact": round(contribution*100, 4)
                })
            
            # If parsed stocks cover less than what TEFAS says, add the remainder as BIST average
            missing_hisse_weight = max(0, tefas_hisse_weight - stocks_total_weight)
            if missing_hisse_weight > 0.01:
                contribution = missing_hisse_weight * bist
                stocks_calculated_return += contribution
                details.append({
                    "asset": "Diğer Hisseler (BIST100 Ort.)", 
                    "weight": round(missing_hisse_weight*100, 2), 
                    "daily_return": round(bist*100, 2),
                    "impact": round(contribution*100, 4)
                })
            
            estimate += stocks_calculated_return
            mode = "Deep Scan (Specific Holdings)"
        else:
            mode = "Category Average (BIST100 Indexed)"
            
        # Add other assets from general allocation
        if alloc:
            for asset in alloc:
                name = asset.get("asset_name", "").lower()
                weight = asset.get("weight", 0) / 100
                impact = 0.0
                
                if any(x in name for x in ["hisse senedi", "stock", "equity"]):
                    if not holdings:
                        impact = bist
                    else:
                        continue # Handled by Deep Scan
                elif any(x in name for x in ["döviz", "eur", "usd", "yabancı", "fx", "foreign", "currency"]): 
                    impact = daily_fixed * 2 # Proxy for fx if we can't reliably get USDTRY
                elif any(x in name for x in ["altın", "kıymetli", "gold", "precious"]): 
                    impact = daily_fixed * 2
                elif any(x in name for x in ["repo", "mevduat", "tahvil", "borçlanma", "para piyasası", "deposit", "bond", "bill", "money market", "paper"]): 
                    impact = daily_fixed
                
                # Only add if it's not hisse senedi handled by Deep Scan
                if impact != 0.0 or not holdings or not any(x in name for x in ["hisse senedi", "stock", "equity"]):
                    contribution = weight * impact
                    estimate += contribution
                    details.append({"asset": asset.get("asset_name"), "weight": round(weight*100, 2), "impact": round(impact*100, 4)})

        return {
            "fund_code": code,
            "estimated_daily_return": round(estimate * 100, 3),
            "calculation_mode": mode,
            "last_allocation_date": info.get("date"),
            "breakdown": details,
            "benchmarks": {"bist100": round(bist*100, 2), "usdtry": 0, "gold": 0}
        }
    return get_cached_realtime(f"FUND_EST_{code}", fetch)

@app.get("/funds/list")
def list_funds(fund_type: str = "YAT"):
    """
    Returns a complete list of all active funds from TEFAS (v1.0.8).
    Default fund_type is 'YAT' (Yatırım Fonu). Use 'EYF' for Pension Funds.
    """
    def fetch():
        return df_to_json(screen_funds(fund_type=fund_type))
    return get_cached_static(f"FUNDS_LIST_{fund_type}", fetch)

@app.get("/funds/screener")
def tefas_screener(fund_type: str = "YAT"):
    def fetch():
        return df_to_json(screen_funds(fund_type=fund_type))
    return get_cached_market(f"FUND_SCREENER_{fund_type}", fetch)

# --- ENDPOINTS: MARKET INSIGHTS (Ultra-Pro) ---

@app.get("/market/breadth")
@limiter.limit("5/minute")
def get_market_breadth(request: Request):
    """
    Returns Advance/Decline ratio for the entire BIST.
    Determines if the 'Whole Market' is bullish or bearish beyond index movement.
    """
    def fetch():
        try:
            from tradingview_screener import Query
            _, df = Query().set_markets('turkey').select('name', 'change', 'volume', 'sector').get_scanner_data()
            
            if df.empty: return {"error": "Breadth data unavailable"}
            
            changes = df['change'].astype(float)
            vols = df['volume'].astype(float)
            
            up_mask = changes > 0
            down_mask = changes < 0
            neutral_mask = changes == 0
            
            up = int(up_mask.sum())
            down = int(down_mask.sum())
            neutral = int(neutral_mask.sum())
            
            return {
                "up": up,
                "down": down,
                "neutral": neutral,
                "up_volume": float(vols[up_mask].sum()),
                "down_volume": float(vols[down_mask].sum()),
                "neutral_volume": float(vols[neutral_mask].sum()),
                "ratio": round(up/down, 2) if down > 0 else up,
                "sentiment": "BULLISH" if up > down * 1.5 else ("BEARISH" if down > up * 1.5 else "NEUTRAL"),
                "sample_size": len(changes)
            }
        except Exception as e:
            return {"error": str(e)}
    return get_cached_realtime("MARKET_BREADTH", fetch)

@app.get("/market/heatmap")
def get_market_heatmap():
    """
    Returns Sector-based performance grouping for Heatmap visualization.
    """
    def fetch():
        try:
            from tradingview_screener import Query
            _, df = Query().set_markets('turkey').select('name', 'change', 'volume', 'sector').get_scanner_data()
            
            if df.empty: return {"error": "Heatmap data currently unavailable"}
            
            heatmap = []
            for _, row in df.head(50).iterrows():
                heatmap.append({
                    "symbol": row.get("name"),
                    "change": round(float(row.get("change", 0)), 2),
                    "volume": float(row.get("volume", 0)),
                    "sector": str(row.get("sector", "N/A"))
                })
            return heatmap
        except Exception as e:
            return {"error": str(e)}
    return get_cached_market("MARKET_HEATMAP", fetch)

@app.get("/market/economy/rates")
def get_tcmb_rates():
    """
    Returns latest interest rates from TCMB.
    """
    def fetch():
        try:
            return df_to_json(TCMB().rates)
        except Exception as e:
            return {"error": f"TCMB Provider Error: {str(e)}"}
    return get_cached_static("TCMB_RATES", fetch)

@app.get("/market/economy/calendar")
def get_economic_calendar(scope: str = "today"):
    """
    Returns upcoming global and local economic events: 'today', 'week', 'month' (v1.1.0).
    """
    def fetch():
        cal = EconomicCalendar()
        if scope == "week": df = cal.this_week()
        elif scope == "month": df = cal.this_month()
        else: df = cal.today()
        return df_to_json(df)
    return get_cached_market(f"CALENDAR_{scope}", fetch)

# --- ENDPOINTS: VIOP ---
@app.get("/viop/list")
def viop_list(category: str = "all"):
    def fetch():
        v = VIOP()
        if category == "stock": return df_to_json(v.stock_futures)
        return df_to_json(v.futures)
    return get_cached_market(f"VIOP_LIST_{category}", fetch)

# --- ENDPOINTS: MACRO ---
@app.get("/market/economy/inflation")
def inflation_data():
    def fetch():
        inf = Inflation()
        return {"tufe": inf.latest("tufe"), "ufe": inf.latest("ufe")}
    return get_cached_static("INFLATION", fetch)

@app.get("/market/tax")
def tax_table():
    return get_cached_static("TAX_TABLE", lambda: df_to_json(tax.withholding_tax_table()))

# --- ENDPOINTS: SEARCH ---
# --- ENDPOINTS: TWITTER (Enhanced Dynamic Auth) ---
@app.get("/search/tweets")
def twitter_search(
    q: str, 
    limit: int = 15, 
    auth_token: Optional[str] = Query(None, description="Twitter auth_token cookie"),
    ct0: Optional[str] = Query(None, description="Twitter ct0 cookie")
):
    """
    Search Twitter/X for tweets. (v1.0.7 - Dynamic Session Support)
    Allows users to provide their own session tokens.
    """
    def fetch():
        with twitter_lock:
            try:
                env_token = os.getenv("TWITTER_AUTH_TOKEN")
                env_ct0 = os.getenv("TWITTER_CT0")
                
                if auth_token and ct0:
                    set_twitter_auth(auth_token=auth_token, ct0=ct0)
                elif env_token and env_ct0:
                    set_twitter_auth(auth_token=env_token, ct0=env_ct0)
                else: 
                    return {"error": "Twitter authentication required. Please provide auth_token and ct0 parameters."}
                
                results = df_to_json(search_tweets(q, limit=limit))
                
                if env_token and env_ct0:
                    set_twitter_auth(auth_token=env_token, ct0=env_ct0)
                else:
                    clear_twitter_auth()
                    
                return results
            except Exception as e:
                return {"error": f"Twitter Search Failed: {str(e)}"}

    return get_cached_realtime(f"TWITTER_{q}_{limit}_{auth_token is not None}", fetch)

@app.get("/search")
def global_search(q: str):
    def fetch(): return df_to_json(market.search_companies(q))
    return get_cached_market(f"SEARCH_{q}", fetch)

@app.get("/search/tweets")
def twitter_search(q: str, limit: int = 15):
    try:
        def fetch(): return df_to_json(search_tweets(query=q, limit=limit))
        return get_cached_market(f"TWEETS_{q}", fetch)
    except: return []

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

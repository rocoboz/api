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
            
        all_symbols = re.findall(r'\n([A-Z]{4,5})\s*\n', text)
        for sym in all_symbols:
            if not bist_tickers or sym not in bist_tickers: continue
            
            sym_pos = text.find(sym)
            if sym_pos == -1: continue
            
            search_window = text[sym_pos:sym_pos+300]
            
            # Robust KAP PDR table matcher
            weight_match = re.search(r'(\d+,\d{2})\s*\n\s*(\d+,\d{2})\s*\n\s*(?:TL|TRY|USD|EUR)', search_window)
            if weight_match:
                val = weight_match.group(1) # FPD (Fund Portfolio Value)
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

# --- CACHING SYSTEM (v1.0.7 Optimized) ---
REALTIME_CACHE = TTLCache(maxsize=500, ttl=10) # Price, Depth (10s)
MARKET_CACHE = TTLCache(maxsize=200, ttl=60) # Screener, VIOP (60s)
STATIC_CACHE = TTLCache(maxsize=1000, ttl=86400) # Info, Tax, Inflation (24h)

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
    # Clean NaN/Inf for JSON
    df = df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)
    return df.to_dict(orient="records")

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
        "github": "https://github.com/saidsurucu/borsapy-api",
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
            
        # Add KAP Details
        try:
            kap = get_kap_provider()
            info['details'] = kap.get_company_details(symbol)
        except: info['details'] = {}
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
def stock_screener(template: Optional[str] = None, pe_max: Optional[float] = None):
    def fetch():
        s = screener.Screener()
        if pe_max: s.add_filter("pe", max=pe_max)
        df = s.run(template=template)
        # Simplified mapping
        data = []
        for _, row in df.iterrows():
            data.append({"symbol": row.get("symbol"), "price": row.get("criteria_7"), "pe": row.get("criteria_28")})
        return data
    return get_cached_market(f"SCREENER_{template}_{pe_max}", fetch)

@app.get("/analysis/{symbol}")
def get_analysis_pro(symbol: str):
    symbol = symbol.upper()
    def fetch():
        tk = Ticker(symbol)
        df = tk.history(period="1y")
        if df.empty: return {"error": "No history"}
        rsi = technical.calculate_rsi(df).iloc[-1]
        supertrend = technical.calculate_supertrend(df).iloc[-1]
        return {
            "symbol": symbol,
            "rsi": round(rsi, 2) if not np.isnan(rsi) else None,
            "supertrend": round(supertrend["Supertrend"], 2) if "Supertrend" in supertrend else None,
            "signal": "BUY" if rsi < 35 else ("SELL" if rsi > 70 else "NEUTRAL")
        }
    return get_cached_market(f"ANALYSIS_PRO_{symbol}", fetch)

# --- ENDPOINTS: FUNDS ---

@app.get("/funds/{code}/estimated-return")
@limiter.limit("20/minute")
def get_fund_estimated_return(request: Request, code: str):
    """
    Calculates estimated daily return based on latest allocation and market prices.
    v1.0.7 - Deep Scan Integration (No-LLM)
    """
    code = code.upper()
    def fetch():
        f = Fund(code)
        info = f.info
        
        # 1. Try Deep Parsing (Specific Holdings) - Cache for 24h
        holdings = get_cached_static(f"DEEP_HOLDINGS_{code}", lambda: parse_fund_holdings_no_llm(code))
        
        # Market Benchmarks
        try:
            bist = Index("XU100").info.get("daily_return", 0) / 100
        except: bist = 0
        try:
            usd = FX("USDTRY").info.get("daily_return", 0) / 100
        except: usd = 0
        try:
            gold = (FX("XAUUSD").info.get("daily_return", 0) / 100) + usd
        except: gold = 0
        
        daily_fixed = 0.0012
        estimate = 0.0
        details = []
        
        # If we have specific holdings, use them for the "Hisse Senedi" portion
        if holdings:
            # Sort and limit to top 15 for performance
            holdings = sorted(holdings, key=lambda x: x['weight'], reverse=True)[:15]
            
            stocks_total_weight = 0
            stocks_calculated_return = 0
            
            from concurrent.futures import ThreadPoolExecutor
            
            def get_stock_ret(h):
                sym = h['symbol']
                weight = h['weight'] / 100
                try:
                    s_info = dict(Ticker(sym).fast_info)
                    s_ret = s_info.get("daily_return", 0) / 100
                except: s_ret = bist
                return {"sym": sym, "weight": weight, "ret": s_ret}

            with ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(get_stock_ret, holdings))
            
            for r in results:
                contribution = r['weight'] * r['ret']
                stocks_calculated_return += contribution
                stocks_total_weight += r['weight']
                details.append({
                    "asset": r['sym'], 
                    "weight": round(r['weight']*100, 2), 
                    "daily_return": round(r['ret']*100, 2),
                    "impact": round(contribution*100, 4)
                })
            
            # Add other assets from general allocation (subtracting what we parsed as stocks)
            alloc = info.get("allocation", [])
            for asset in alloc:
                name = asset.get("asset_name", "").lower()
                weight = asset.get("weight", 0) / 100
                
                # Skip the portion we already calculated specifically
                if "hisse senedi" in name:
                    # If parsing found more/less stocks than TEFAS summary, we normalize
                    continue 

                impact = 0.0
                if "döviz" in name or "eur" in name or "usd" in name: impact = usd
                elif "altın" in name or "kıymetli" in name: impact = gold
                elif "repo" in name or "mevduat" in name or "tahvil" in name: impact = daily_fixed
                
                contribution = weight * impact
                estimate += contribution
                details.append({"asset": asset.get("asset_name"), "weight": round(weight*100, 2), "impact": round(impact*100, 4)})
            
            estimate += stocks_calculated_return
            mode = "Deep Scan (Specific Holdings)"
        else:
            # Fallback to Category-based estimation
            alloc = info.get("allocation", [])
            if not alloc: return {"error": "Allocation data not available"}
            
            for asset in alloc:
                name = asset.get("asset_name", "").lower()
                weight = asset.get("weight", 0) / 100
                impact = 0.0
                if "hisse senedi" in name: impact = bist
                elif "döviz" in name or "eur" in name or "usd" in name: impact = usd
                elif "altın" in name or "kıymetli" in name: impact = gold
                elif "repo" in name or "mevduat" in name or "tahvil" in name: impact = daily_fixed
                
                contribution = weight * impact
                estimate += contribution
                details.append({"asset": asset.get("asset_name"), "weight": round(weight*100, 2), "impact": round(impact*100, 4)})
            mode = "Category Average (BIST100 Indexed)"

        return {
            "fund_code": code,
            "estimated_daily_return": round(estimate * 100, 3),
            "calculation_mode": mode,
            "last_allocation_date": info.get("date"),
            "breakdown": details,
            "benchmarks": {"bist100": bist*100, "usdtry": usd*100, "gold": gold*100}
        }
    return get_cached_realtime(f"FUND_EST_{code}", fetch)

@app.get("/funds/screener")
def tefas_screener(category: Optional[str] = None):
    def fetch():
        return df_to_json(screen_funds(category=category))
    return get_cached_market(f"FUND_SCREENER_{category}", fetch)

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
            
            up = int((changes > 0).sum())
            down = int((changes < 0).sum())
            neutral = int((changes == 0).sum())
            
            return {
                "up": up,
                "down": down,
                "neutral": neutral,
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

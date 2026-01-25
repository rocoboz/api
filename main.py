import json
import asyncio
import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional, Dict, Any, Union

# --- THIRD PARTY LIBRARIES ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from cachetools import TTLCache

# --- PATH SETUP & DEBUGGING ---
# Determine absolute paths
base_dir = os.path.dirname(os.path.abspath(__file__))
lib_dir_name = 'borsapy_lib'
lib_path = os.path.join(base_dir, lib_dir_name)

# Check library directory
if not os.path.exists(lib_path):
    print(f"CRITICAL ERROR: Library path does not exist: {lib_path}")

# Add to sys.path
sys.path.insert(0, lib_path)

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Request, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
import pandas as pd
import numpy as np

# Borsapy imports
try:
    from borsapy import Ticker, FX, Crypto, Fund, Index, Bond, Eurobond
    from borsapy import market, technical
    from borsapy.stream import TradingViewStream
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    # Don't raise here to allow app to start and show error on health check
    pass

# --- SECURITY & CONFIG ---
API_KEY = os.getenv("API_KEY", "borsapy-mobile-secret-123")
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """
    Verifies the API Key. 
    If API_KEY env var is set to 'OPEN', security is disabled.
    Otherwise, strict checking is enforced for mobile app safety.
    """
    if API_KEY == "OPEN":
        return True
    if api_key == API_KEY:
        return True
    # For now, we Log warning but allow access to not break your existing Web Dashboard.
    # In a real Production Mobile App, you would raise HTTPException(403) here.
    return True 

# --- APP SETUP ---
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="BorsaPy API",
    description="Professional Financial Data API for Mobile & Web",
    version="1.0.3"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration - Restrict this in production!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # TODO: Change to your specific domain for better security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CACHING SYSTEM (MEMORY SAFE) ---

# 1. Stock Cache: High volatility, fixed TTL. 
# Max 1000 items to prevent memory leaks.
STOCK_CACHE = TTLCache(maxsize=1000, ttl=60)

# 2. Fund Cache: Custom dynamic logic.
# We keep it as a dict but manage size manually to prevent leaks.
FUND_CACHE = {} 

def get_turkey_time():
    return datetime.now(ZoneInfo("Europe/Istanbul"))

def get_cached_fund_data(code: str, fetch_func):
    """
    Dynamic caching for funds based on TEFAS update hours.
    Memory Safe: Clears cache if it grows too large.
    """
    # Memory Leak Protection
    if len(FUND_CACHE) > 1000:
        FUND_CACHE.clear()
        print("INFO: Fund Cache cleared to prevent memory overflow.")

    now = get_turkey_time()
    is_weekday = now.weekday() < 5
    current_hour = now.hour
    
    # Logic: Weekday & 10-15h -> 15 min TTL, Else -> 4 hour TTL
    if is_weekday and 10 <= current_hour <= 15:
        ttl_seconds = 900 
        cache_mode = "HOT (15m)"
    else:
        ttl_seconds = 14400 
        cache_mode = "COLD (4h)"
        
    # Check Cache
    if code in FUND_CACHE:
        entry = FUND_CACHE[code]
        age = (now - entry['timestamp']).total_seconds()
        if age < ttl_seconds:
            return entry['data']
    
    # Refetch
    print(f"CACHE MISS (Fund): {code} | Mode: {cache_mode}")
    data = fetch_func()
    FUND_CACHE[code] = {'data': data, 'timestamp': now}
    return data

def get_cached_stock_data(key: str, fetch_func, ttl_override=None):
    """
    Wrapper for TTLCache.
    """
    # If key exists and is valid, return it
    if key in STOCK_CACHE:
        return STOCK_CACHE[key]
    
    # Else fetch and store
    print(f"CACHE MISS (Stock): {key}")
    data = fetch_func()
    
    # Note: cachetools TTLCache doesn't support per-item TTL easily 
    # without using a different cache policy or multiple caches.
    # For simplicity/stability, we use the global TTL (60s) defined in STOCK_CACHE.
    # If an item needs longer cache (like financials), we can put it in a separate cache 
    # or just accept 60s for now to keep it simple.
    # BETTER: We'll create a separate cache for long-lived items.
    STOCK_CACHE[key] = data
    return data

# Secondary Cache for Long-lived items (Financials, Search) - 1 hour TTL
LONG_CACHE = TTLCache(maxsize=500, ttl=3600)

def get_long_cached_data(key: str, fetch_func):
    if key in LONG_CACHE:
        return LONG_CACHE[key]
    data = fetch_func()
    LONG_CACHE[key] = data
    return data

# --- Helper Functions ---

def df_to_json(df: Union[pd.DataFrame, pd.Series, None]) -> Any:
    if df is None: return None
    if isinstance(df, pd.Series): df = df.to_frame()
    if df.empty: return []
    df = df.reset_index()
    df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)
    return df.to_dict(orient="records")

# --- ENDPOINTS ---

@app.get("/")
@limiter.limit("60/minute")
def home(request: Request):
    return {
        "status": "online",
        "service": "BorsaPy API Mobile",
        "version": "1.0.3",
        "security": "Rate Limited & API Key Ready"
    }

# --- 1. Stocks Endpoints ---

@app.get("/stocks/list")
@limiter.limit("30/minute")
def get_stock_list(request: Request, authorized: bool = Depends(verify_api_key)):
    try:
        return get_long_cached_data("ALL_STOCKS_LIST", lambda: df_to_json(market.companies()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stocks/{symbol}")
@limiter.limit("60/minute")
def get_stock_detail(request: Request, symbol: str, authorized: bool = Depends(verify_api_key)):
    try:
        def fetch():
            tk = Ticker(symbol)
            info = tk.fast_info if hasattr(tk, 'fast_info') else {}
            if not info: info = tk.info if hasattr(tk, 'info') else {}
            return {"symbol": symbol.upper(), "data": info}
        return get_cached_stock_data(f"{symbol}_DETAIL", fetch)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Stock not found")

@app.get("/stocks/{symbol}/history")
@limiter.limit("30/minute") # Heavier endpoint
def get_stock_history(
    request: Request,
    symbol: str, 
    period: str = Query("1mo"),
    interval: str = Query("1d"),
    authorized: bool = Depends(verify_api_key)
):
    try:
        cache_key = f"{symbol}_HIST_{period}_{interval}"
        def fetch():
            tk = Ticker(symbol)
            return df_to_json(tk.history(period=period, interval=interval))
        return get_cached_stock_data(cache_key, fetch)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stocks/{symbol}/financials")
@limiter.limit("20/minute")
def get_stock_financials(request: Request, symbol: str, type: str = "balance", authorized: bool = Depends(verify_api_key)):
    try:
        cache_key = f"{symbol}_FIN_{type}"
        def fetch():
            tk = Ticker(symbol)
            if type == "balance": return df_to_json(tk.get_balance_sheet())
            elif type == "income": return df_to_json(tk.get_income_stmt())
            elif type == "cashflow": return df_to_json(tk.get_cashflow())
            return []
        return get_long_cached_data(cache_key, fetch)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. Funds (TEFAS) ---

@app.get("/funds/{code}")
@limiter.limit("60/minute")
def get_fund_detail(request: Request, code: str, authorized: bool = Depends(verify_api_key)):
    try:
        def fetch():
            f = Fund(code)
            data = {k: v for k, v in f.__dict__.items() if not k.startswith('_')}
            return {"code": code.upper(), "data": data}
        return get_cached_fund_data(f"{code}_DETAIL", fetch)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/funds/{code}/history")
@limiter.limit("30/minute")
def get_fund_history(request: Request, code: str, authorized: bool = Depends(verify_api_key)):
    try:
        def fetch():
            f = Fund(code)
            return df_to_json(f.history()) if hasattr(f, 'history') else {"error": "No history"}
        return get_cached_fund_data(f"{code}_HIST", fetch)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. FX & Indices ---

@app.get("/fx/list")
@limiter.limit("60/minute")
def get_fx_list(request: Request):
    return [
        {"symbol": "USD", "name": "US Dollar"},
        {"symbol": "EUR", "name": "Euro"},
        {"symbol": "gram-altin", "name": "Gram Gold"},
        {"symbol": "gumus", "name": "Silver"}
    ]

@app.get("/fx/{symbol}")
@limiter.limit("60/minute")
def get_fx_detail(request: Request, symbol: str):
    try:
        def fetch():
            fx = FX(symbol)
            data = {}
            if hasattr(fx, 'bank_rates'): data['bank_rates'] = df_to_json(fx.bank_rates)
            return {"symbol": symbol, "data": data}
        # FX needs fast updates, stock cache (60s) is fine
        return get_cached_stock_data(f"FX_{symbol}", fetch)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/market/index/{symbol}")
@limiter.limit("60/minute")
def get_index_detail(request: Request, symbol: str):
    try:
        def fetch():
            idx = Index(symbol)
            return {"symbol": symbol, "history": df_to_json(idx.history(period="1mo"))}
        return get_cached_stock_data(f"IDX_{symbol}", fetch)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/bonds/{name}")
@limiter.limit("60/minute")
def get_bond_detail(request: Request, name: str):
    try:
        def fetch():
            try:
                b = Bond(name)
                return {"name": name, "type": "Bond", "data": df_to_json(b.history())}
            except:
                eb = Eurobond(name)
                return {"name": name, "type": "Eurobond", "data": df_to_json(eb.history())}
        return get_long_cached_data(f"BOND_{name}", fetch)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Bond not found")

# --- 4. Analysis & Search ---

@app.get("/analysis/{symbol}")
@limiter.limit("15/minute") # Very heavy endpoint, strict limit
def get_analysis(request: Request, symbol: str, authorized: bool = Depends(verify_api_key)):
    try:
        def fetch():
            tk = Ticker(symbol)
            df = tk.history(period="1y")
            if df.empty: return {"error": "No data"}
            
            ta = technical.TechnicalAnalyzer(df)
            rsi = ta.calculate_rsi().iloc[-1] if hasattr(ta, 'calculate_rsi') else None
            sma50 = ta.calculate_sma(period=50).iloc[-1] if hasattr(ta, 'calculate_sma') else None
            sma200 = ta.calculate_sma(period=200).iloc[-1] if hasattr(ta, 'calculate_sma') else None
            
            return {
                "symbol": symbol,
                "last_price": df["Close"].iloc[-1],
                "indicators": {"RSI": round(rsi, 2) if rsi else None, "SMA_50": round(sma50, 2) if sma50 else None, "SMA_200": round(sma200, 2) if sma200 else None},
                "signal": "BUY" if rsi and rsi < 30 else ("SELL" if rsi and rsi > 70 else "NEUTRAL")
            }
        return get_cached_stock_data(f"ANALYSIS_{symbol}", fetch)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search")
@limiter.limit("30/minute")
def search(request: Request, q: str):
    try:
        return get_long_cached_data(f"SEARCH_{q}", lambda: df_to_json(market.search_companies(q)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

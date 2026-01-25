import json
import asyncio
import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional, Dict, Any, Union

# --- PATH SETUP & DEBUGGING ---
# Determine absolute paths
base_dir = os.path.dirname(os.path.abspath(__file__))
lib_dir_name = 'borsapy_lib'
lib_path = os.path.join(base_dir, lib_dir_name)

print("--- DEBUG START ---")
print(f"Current Working Directory: {os.getcwd()}")
print(f"Script Directory: {base_dir}")
print(f"Library Path: {lib_path}")

# Check library directory
if os.path.exists(lib_path):
    print(f"Library directory exists: {lib_path}")
    try:
        contents = os.listdir(lib_path)
        print(f"Contents of {lib_dir_name}: {contents}")
        
        # Check for inner borsapy package
        borsapy_inner = os.path.join(lib_path, 'borsapy')
        if os.path.exists(borsapy_inner):
            print(f"Found 'borsapy' package folder: {borsapy_inner}")
            try:
                print(f"Contents of borsapy package: {os.listdir(borsapy_inner)}")
            except Exception as e:
                print(f"Error listing borsapy package contents: {e}")
        else:
            print(f"WARNING: 'borsapy' folder not found inside {lib_path}")
            
    except Exception as e:
        print(f"Error listing directory contents: {e}")
else:
    print(f"CRITICAL ERROR: Library path does not exist: {lib_path}")

# Add to sys.path
sys.path.insert(0, lib_path)
print(f"sys.path[0]: {sys.path[0]}")
print("--- DEBUG END ---")

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np

# Borsapy imports
try:
    from borsapy import Ticker, FX, Crypto, Fund, Index, Bond, Eurobond
    from borsapy import market, technical
    from borsapy.stream import TradingViewStream
    print("SUCCESS: borsapy imported successfully.")
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    raise e

app = FastAPI(
    title="BorsaPy API",
    description="Professional Financial Data API for BIST, Forex, Crypto and Funds",
    version="1.0.2"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CACHING SYSTEM ---

FUND_CACHE = {} # {code: {'data': ..., 'timestamp': datetime}}
STOCK_CACHE = {} # {symbol: {'data': ..., 'timestamp': datetime}}

def get_turkey_time():
    return datetime.now(ZoneInfo("Europe/Istanbul"))

def get_cached_fund_data(code: str, fetch_func):
    """
    Dynamic caching for funds based on TEFAS update hours.
    Updates usually happen on weekdays between 10:00 and 14:00.
    """
    now = get_turkey_time()
    
    # Check if it's a weekday (0=Monday, 4=Friday)
    is_weekday = now.weekday() < 5
    current_hour = now.hour
    
    # Logic:
    # If it's a Weekday AND between 10:00 and 15:00 (Hot Zone) -> Short Cache (15 mins)
    # Otherwise (Weekends or Evenings) -> Long Cache (4 hours)
    
    if is_weekday and 10 <= current_hour <= 14:
        # High frequency update window (10, 11, 12, 13, 14 hours)
        ttl_seconds = 900 # 15 minutes
        cache_mode = "HOT (15m)"
    else:
        # Market closed / No updates expected
        ttl_seconds = 14400 # 4 hours
        cache_mode = "COLD (4h)"
        
    # Check Cache
    if code in FUND_CACHE:
        entry = FUND_CACHE[code]
        age = (now - entry['timestamp']).total_seconds()
        
        if age < ttl_seconds:
            # print(f"CACHE HIT (Fund): {code} | Age: {age:.0f}s | Mode: {cache_mode}")
            return entry['data']
    
    # Refetch
    print(f"CACHE MISS (Fund): {code} | Mode: {cache_mode} - Refetching...")
    data = fetch_func()
    FUND_CACHE[code] = {'data': data, 'timestamp': now}
    return data

def get_cached_stock_data(symbol: str, fetch_func, ttl_seconds=60):
    """
    Simple TTL cache for stocks (high volatility).
    Default 60 seconds to prevent abuse but allow near-realtime.
    """
    now = get_turkey_time()
    
    if symbol in STOCK_CACHE:
        entry = STOCK_CACHE[symbol]
        if (now - entry['timestamp']).total_seconds() < ttl_seconds:
            # print(f"CACHE HIT (Stock): {symbol}")
            return entry['data']

    # Refetch
    print(f"CACHE MISS (Stock): {symbol} - Refetching...")
    data = fetch_func()
    STOCK_CACHE[symbol] = {'data': data, 'timestamp': now}
    return data

# --- Helper Functions ---

def df_to_json(df: Union[pd.DataFrame, pd.Series, None]) -> Any:
    """Converts Pandas DataFrame/Series to a JSON-friendly list of dicts."""
    if df is None:
        return None
    if isinstance(df, pd.Series):
        df = df.to_frame()
    if df.empty:
        return []
    
    # Reset index to include Date/Time columns if they are in the index
    df = df.reset_index()
    
    # Handle NaN/Inf values which break JSON
    df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
    
    # Convert Timestamp objects to string
    # Try to find date columns
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)
            
    return df.to_dict(orient="records")

# --- Root Endpoint ---
@app.get("/")
def home():
    return {
        "status": "online",
        "service": "BorsaPy API",
        "version": "1.0.2",
        "endpoints": {
            "stocks": "/stocks/list",
            "stock_detail": "/stocks/{symbol}",
            "funds": "/funds/{code}",
            "fx": "/fx/USD",
            "indices": "/market/index/XU100",
            "bonds": "/bonds/TRT123456",
            "crypto": "/crypto/BTCTRY",
            "analysis": "/analysis/{symbol}",
            "search": "/search?q=query"
        }
    }

# --- 1. Stocks Endpoints ---

@app.get("/stocks/list")
def get_stock_list():
    """Returns a list of all BIST companies."""
    try:
        # Assuming market.companies() returns a DataFrame
        # Cache list for 1 hour as it rarely changes
        def fetch():
            return df_to_json(market.companies())
            
        # Unique key for list
        return get_cached_stock_data("ALL_STOCKS_LIST", fetch, ttl_seconds=3600)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stocks/{symbol}")
def get_stock_detail(symbol: str):
    """Get stock summary, price, and basic info."""
    try:
        def fetch():
            tk = Ticker(symbol)
            info = tk.fast_info if hasattr(tk, 'fast_info') else {}
            if not info:
                 info = tk.info if hasattr(tk, 'info') else {}
            return {
                "symbol": symbol.upper(),
                "data": info
            }
            
        return get_cached_stock_data(f"{symbol}_DETAIL", fetch, ttl_seconds=60)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Stock not found or error: {str(e)}")

@app.get("/stocks/{symbol}/history")
def get_stock_history(
    symbol: str, 
    period: str = Query("1mo", description="1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max"),
    interval: str = Query("1d", description="1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo")
):
    """Get historical OHLCV data."""
    try:
        # Cache key depends on args
        cache_key = f"{symbol}_HIST_{period}_{interval}"
        
        def fetch():
            tk = Ticker(symbol)
            df = tk.history(period=period, interval=interval)
            return df_to_json(df)
            
        return get_cached_stock_data(cache_key, fetch, ttl_seconds=60)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stocks/{symbol}/financials")
def get_stock_financials(symbol: str, type: str = Query("balance", enum=["balance", "income", "cashflow"])):
    """Get financial statements."""
    try:
        # Financials update quarterly, cache for 24 hours
        cache_key = f"{symbol}_FIN_{type}"
        
        def fetch():
            tk = Ticker(symbol)
            df = None
            if type == "balance":
                df = tk.get_balance_sheet()
            elif type == "income":
                df = tk.get_income_stmt()
            elif type == "cashflow":
                df = tk.get_cashflow()
            return df_to_json(df)
            
        return get_cached_stock_data(cache_key, fetch, ttl_seconds=86400)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. Funds (TEFAS) ---

@app.get("/funds/{code}")
def get_fund_detail(code: str):
    """Get TEFAS fund details."""
    try:
        def fetch():
            f = Fund(code)
            data = {k: v for k, v in f.__dict__.items() if not k.startswith('_')}
            return {"code": code.upper(), "data": data}
            
        # Use Smart Fund Caching
        return get_cached_fund_data(f"{code}_DETAIL", fetch)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/funds/{code}/history")
def get_fund_history(code: str):
    """Get TEFAS fund historical price."""
    try:
        def fetch():
            f = Fund(code)
            if hasattr(f, 'history'):
                 return df_to_json(f.history())
            return {"error": "History not available for this fund type"}
            
        # Use Smart Fund Caching
        return get_cached_fund_data(f"{code}_HIST", fetch)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. FX & Commodities ---

@app.get("/fx/list")
def get_fx_list():
    """List common FX and commodities."""
    # Static list, infinite cache technically fine, but let's keep it simple
    return [
        {"symbol": "USD", "name": "US Dollar"},
        {"symbol": "EUR", "name": "Euro"},
        {"symbol": "gram-altin", "name": "Gram Gold"},
        {"symbol": "ceyrek-altin", "name": "Quarter Gold"},
        {"symbol": "gumus", "name": "Silver"}
    ]

@app.get("/fx/{symbol}")
def get_fx_detail(symbol: str):
    """Get FX rates (including bank rates)."""
    try:
        def fetch():
            fx = FX(symbol)
            data = {}
            if hasattr(fx, 'bank_rates'):
                 data['bank_rates'] = df_to_json(fx.bank_rates)
            return {"symbol": symbol, "data": data}
            
        # FX rates update frequently, cache for 5 mins
        return get_cached_stock_data(f"FX_{symbol}", fetch, ttl_seconds=300)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
        
# --- 3.1 Bonds & Eurobonds & Indices (New) ---

@app.get("/market/index/{symbol}")
def get_index_detail(symbol: str):
    """Get Market Index details (e.g. XU100)."""
    try:
        def fetch():
            idx = Index(symbol)
            df = idx.history(period="1mo")
            return {
                "symbol": symbol,
                "history": df_to_json(df)
            }
        
        # Indices are live like stocks
        return get_cached_stock_data(f"IDX_{symbol}", fetch, ttl_seconds=60)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/bonds/{name}")
def get_bond_detail(name: str):
    """Get Bond/Eurobond details."""
    try:
        def fetch():
            try:
                b = Bond(name)
                return {"name": name, "type": "Bond", "data": df_to_json(b.history())}
            except:
                eb = Eurobond(name)
                return {"name": name, "type": "Eurobond", "data": df_to_json(eb.history())}
                
        # Bonds trade daily usually, cache for 4 hours
        return get_cached_stock_data(f"BOND_{name}", fetch, ttl_seconds=14400)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Bond/Eurobond not found")

# --- 4. Crypto ---

@app.get("/crypto/{symbol}")
def get_crypto_detail(symbol: str):
    try:
        # Placeholder
        return {"symbol": symbol, "data": "Not fully implemented yet (check borsapy docs)"}
    except Exception as e:
         raise HTTPException(status_code=404, detail=str(e))

# --- 5. Analysis & Search ---

@app.get("/analysis/{symbol}")
def get_analysis(symbol: str):
    """Perform technical analysis on the symbol."""
    try:
        # Analysis is heavy, cache it for 2 minutes
        def fetch():
            tk = Ticker(symbol)
            df = tk.history(period="1y")
            
            if df.empty:
                return {"error": "No data for analysis"}

            ta = technical.TechnicalAnalyzer(df)
            
            # Calculate indicators
            rsi = ta.calculate_rsi().iloc[-1] if hasattr(ta, 'calculate_rsi') else None
            sma_50 = ta.calculate_sma(period=50).iloc[-1] if hasattr(ta, 'calculate_sma') else None
            sma_200 = ta.calculate_sma(period=200).iloc[-1] if hasattr(ta, 'calculate_sma') else None
            
            macd_data = ta.calculate_macd() if hasattr(ta, 'calculate_macd') else pd.DataFrame()
            macd = macd_data.iloc[-1].to_dict() if not macd_data.empty else {}

            return {
                "symbol": symbol,
                "last_price": df["Close"].iloc[-1],
                "indicators": {
                    "RSI": round(rsi, 2) if rsi else None,
                    "SMA_50": round(sma_50, 2) if sma_50 else None,
                    "SMA_200": round(sma_200, 2) if sma_200 else None,
                    "MACD": macd
                },
                "signal": "BUY" if rsi and rsi < 30 else ("SELL" if rsi and rsi > 70 else "NEUTRAL")
            }
            
        return get_cached_stock_data(f"ANALYSIS_{symbol}", fetch, ttl_seconds=120)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search")
def search(q: str):
    """Search for companies or tickers."""
    try:
        # Search results don't change often, cache for 1 hour
        return get_cached_stock_data(f"SEARCH_{q}", lambda: df_to_json(market.search_companies(q)), ttl_seconds=3600)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- WebSocket for Streaming (Experimental) ---
# Note: TradingViewStream usage in a multi-user environment is complex.
# This is a basic echo/status implementation for now.

@app.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # In a real impl, we would interpret 'data' as subscription request
            # e.g., {"action": "subscribe", "symbol": "THYAO"}
            # And then push updates from TradingViewStream.
            
            # Mock response for now
            await websocket.send_text(f"Received: {data}. Streaming not active in this demo.")
    except WebSocketDisconnect:
        print("Client disconnected")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

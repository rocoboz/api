import json
import asyncio
import sys
import os

# Add local borsapy_lib to path to use the latest version
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'borsapy_lib')))

from typing import List, Optional, Dict, Any, Union
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np

# Borsapy imports
from borsapy import Ticker, FX, Crypto, Fund, Index, Bond, Eurobond
from borsapy import market, technical
from borsapy.stream import TradingViewStream

app = FastAPI(
    title="BorsaPy API",
    description="Professional Financial Data API for BIST, Forex, Crypto and Funds",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        "version": "1.0.0",
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
        df = market.companies()
        return df_to_json(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stocks/{symbol}")
def get_stock_detail(symbol: str):
    """Get stock summary, price, and basic info."""
    try:
        tk = Ticker(symbol)
        # Using fast_info for speed if available, else info
        info = tk.fast_info if hasattr(tk, 'fast_info') else {}
        if not info:
             info = tk.info if hasattr(tk, 'info') else {}
             
        return {
            "symbol": symbol.upper(),
            "data": info
        }
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
        tk = Ticker(symbol)
        df = tk.history(period=period, interval=interval)
        return df_to_json(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stocks/{symbol}/financials")
def get_stock_financials(symbol: str, type: str = Query("balance", enum=["balance", "income", "cashflow"])):
    """Get financial statements."""
    try:
        tk = Ticker(symbol)
        df = None
        if type == "balance":
            df = tk.get_balance_sheet()
        elif type == "income":
            df = tk.get_income_stmt() # Adjust method name if needed based on borsapy version
        elif type == "cashflow":
            df = tk.get_cashflow() # Adjust method name if needed
            
        return df_to_json(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. Funds (TEFAS) ---

@app.get("/funds/{code}")
def get_fund_detail(code: str):
    """Get TEFAS fund details."""
    try:
        f = Fund(code)
        # Fund object usually has attributes or a method to get data
        # Inspecting borsapy source implies it might load data on init or via methods
        # We will try to return the dictionary representation of public attributes
        data = {k: v for k, v in f.__dict__.items() if not k.startswith('_')}
        
        # If there's a specific 'history' method or similar, we might want separate endpoint
        return {"code": code.upper(), "data": data}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/funds/{code}/history")
def get_fund_history(code: str):
    """Get TEFAS fund historical price."""
    try:
        f = Fund(code)
        if hasattr(f, 'history'):
             return df_to_json(f.history())
        return {"error": "History not available for this fund type"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. FX & Commodities ---

@app.get("/fx/list")
def get_fx_list():
    """List common FX and commodities."""
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
        fx = FX(symbol)
        # Assuming .current or .bank_rates property
        data = {}
        if hasattr(fx, 'bank_rates'):
             data['bank_rates'] = df_to_json(fx.bank_rates)
        
        return {"symbol": symbol, "data": data}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
        
# --- 3.1 Bonds & Eurobonds & Indices (New) ---

@app.get("/market/index/{symbol}")
def get_index_detail(symbol: str):
    """Get Market Index details (e.g. XU100)."""
    try:
        idx = Index(symbol)
        df = idx.history(period="1mo")
        return {
            "symbol": symbol,
            "history": df_to_json(df)
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/bonds/{name}")
def get_bond_detail(name: str):
    """Get Bond/Eurobond details."""
    try:
        # Try Bond first, then Eurobond
        try:
            b = Bond(name)
            return {"name": name, "type": "Bond", "data": df_to_json(b.history())}
        except:
            eb = Eurobond(name)
            return {"name": name, "type": "Eurobond", "data": df_to_json(eb.history())}
    except Exception as e:
        raise HTTPException(status_code=404, detail="Bond/Eurobond not found")

# --- 4. Crypto ---

@app.get("/crypto/{symbol}")
def get_crypto_detail(symbol: str):
    try:
        c = Crypto(symbol)
        # Implementation depends on borsapy Crypto class structure
        return {"symbol": symbol, "data": "Not fully implemented yet (check borsapy docs)"}
    except Exception as e:
         raise HTTPException(status_code=404, detail=str(e))

# --- 5. Analysis & Search ---

@app.get("/analysis/{symbol}")
def get_analysis(symbol: str):
    """Perform technical analysis on the symbol."""
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search")
def search(q: str):
    """Search for companies or tickers."""
    try:
        res = market.search_companies(q)
        return df_to_json(res)
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

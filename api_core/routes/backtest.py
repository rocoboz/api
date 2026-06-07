from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json
from api_core.services.response import api_ok
from api_core.services.security import limiter
from borsapy import Backtest

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol to backtest (e.g. THYAO)")
    strategy: str = Field(..., description="Strategy name: rsi, sma_crossover, ema_crossover, macd")
    period: str = Field("1y", description="Historical data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y)")
    interval: str = Field("1d", description="Candle interval (1m, 5m, 15m, 30m, 1h, 4h, 1d)")
    capital: float = Field(100000.0, description="Initial starting capital in TL")
    commission: float = Field(0.001, description="Commission rate per trade (e.g. 0.001 for 0.1%)")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Custom settings/parameters for the strategy")


def make_rsi_strategy(lower=30, upper=70, rsi_col="rsi"):
    def strategy(candle, position, indicators):
        rsi_val = indicators.get(rsi_col)
        if rsi_val is None:
            return "HOLD"
        if rsi_val < lower and position is None:
            return "BUY"
        elif rsi_val > upper and position == "long":
            return "SELL"
        return "HOLD"
    return strategy


def make_sma_crossover_strategy(fast=20, slow=50):
    def strategy(candle, position, indicators):
        fast_val = indicators.get(f"sma_{fast}")
        slow_val = indicators.get(f"sma_{slow}")
        if fast_val is None or slow_val is None:
            return "HOLD"
        if fast_val > slow_val and position is None:
            return "BUY"
        elif fast_val < slow_val and position == "long":
            return "SELL"
        return "HOLD"
    return strategy


def make_ema_crossover_strategy(fast=12, slow=26):
    def strategy(candle, position, indicators):
        fast_val = indicators.get(f"ema_{fast}")
        slow_val = indicators.get(f"ema_{slow}")
        if fast_val is None or slow_val is None:
            return "HOLD"
        if fast_val > slow_val and position is None:
            return "BUY"
        elif fast_val < slow_val and position == "long":
            return "SELL"
        return "HOLD"
    return strategy


def make_macd_strategy():
    def strategy(candle, position, indicators):
        macd = indicators.get("macd")
        sig = indicators.get("macd_signal")
        if macd is None or sig is None:
            return "HOLD"
        if macd > sig and position is None:
            return "BUY"
        elif macd < sig and position == "long":
            return "SELL"
        return "HOLD"
    return strategy


@router.post("/run")
@limiter.limit("5/minute")
def run_backtest(request: Request, response: Response, req: BacktestRequest):
    strategy_name = req.strategy.lower()
    params = req.parameters or {}

    # Define strategy function and required indicators
    if strategy_name == "rsi":
        lower = params.get("lower_bound", 30)
        upper = params.get("upper_bound", 70)
        rsi_period = params.get("rsi_period", 14)
        
        rsi_col = "rsi" if rsi_period == 14 else f"rsi_{rsi_period}"
        strategy_func = make_rsi_strategy(lower=lower, upper=upper, rsi_col=rsi_col)
        indicators = [rsi_col]
        
    elif strategy_name == "sma_crossover":
        fast = params.get("fast", 20)
        slow = params.get("slow", 50)
        
        strategy_func = make_sma_crossover_strategy(fast=fast, slow=slow)
        indicators = [f"sma_{fast}", f"sma_{slow}"]
        
    elif strategy_name == "ema_crossover":
        fast = params.get("fast", 12)
        slow = params.get("slow", 26)
        
        strategy_func = make_ema_crossover_strategy(fast=fast, slow=slow)
        indicators = [f"ema_{fast}", f"ema_{slow}"]
        
    elif strategy_name == "macd":
        strategy_func = make_macd_strategy()
        indicators = ["macd"]
        
    else:
        return {"error": f"Invalid strategy '{req.strategy}'. Supported strategies: rsi, sma_crossover, ema_crossover, macd"}

    try:
        bt = Backtest(
            symbol=req.symbol,
            strategy=strategy_func,
            period=req.period,
            interval=req.interval,
            capital=req.capital,
            commission=req.commission,
            indicators=indicators,
        )
        # Rename strategy function name for cleaner JSON representation
        bt._strategy_name = req.strategy
        
        result = bt.run()
        
        # Serialize trades DataFrame
        trades = df_to_json(result.trades_df)
        
        # Serialize curves
        equity_curve = []
        if not result.equity_curve.empty:
            # reset_index to get Date column in json
            equity_curve = df_to_json(result.equity_curve.reset_index(name="equity"))
            
        drawdown_curve = []
        if not result.drawdown_curve.empty:
            drawdown_curve = df_to_json(result.drawdown_curve.reset_index(name="drawdown"))
            
        buy_hold_curve = []
        if not result.buy_hold_curve.empty:
            buy_hold_curve = df_to_json(result.buy_hold_curve.reset_index(name="buy_hold"))

        metrics = result.to_dict()
        cleaned_metrics = {k: clean_json_val(v) for k, v in metrics.items()}

        payload = {
            "metrics": cleaned_metrics,
            "trades": trades,
            "equity_curve": equity_curve,
            "drawdown_curve": drawdown_curve,
            "buy_hold_curve": buy_hold_curve,
        }
        return compact_payload(payload)
    except Exception as exc:
        return {"error": f"Backtest execution failed: {exc}"}

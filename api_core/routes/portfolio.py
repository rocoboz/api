from __future__ import annotations

from typing import List, Optional, Dict
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json
from api_core.services.response import api_ok
from api_core.services.security import limiter
from finans_core import Portfolio

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class HoldingItem(BaseModel):
    symbol: str = Field(..., description="Asset symbol (e.g. THYAO, USD, gram-altin, YAY)")
    shares: float = Field(..., description="Number of shares/units owned")
    cost: Optional[float] = Field(None, description="Purchase cost per share/unit. If None, uses current price")
    asset_type: Optional[str] = Field(None, description="Asset type override: stock, fx, crypto, fund. Auto-detected if None")
    purchase_date: Optional[str] = Field(None, description="Purchase date in YYYY-MM-DD format. Defaults to today if None")


class PortfolioAnalysisRequest(BaseModel):
    holdings: List[HoldingItem] = Field(..., description="List of assets in the portfolio")
    benchmark: str = Field("XU100", description="Benchmark index for beta/alpha calculations")
    period: str = Field("1y", description="Time period for historical calculation (1mo, 3mo, 6mo, 1y)")
    risk_free_rate: Optional[float] = Field(None, description="Annual risk-free rate as decimal (e.g. 0.28 for 28%)")


class PortfolioRebalanceRequest(BaseModel):
    holdings: List[HoldingItem] = Field(..., description="List of current assets in the portfolio")
    target_weights: Dict[str, float] = Field(..., description="Target allocation weights mapping (e.g. {'THYAO': 0.6, 'GARAN': 0.4})")
    threshold: float = Field(0.0, description="Minimum drift threshold to trigger a rebalance action")


@router.post("/analysis")
@limiter.limit("10/minute")
def analyze_portfolio(request: Request, response: Response, req: PortfolioAnalysisRequest):
    try:
        p = Portfolio(benchmark=req.benchmark)
        for item in req.holdings:
            p.add(
                symbol=item.symbol,
                shares=item.shares,
                cost=item.cost,
                asset_type=item.asset_type,
                purchase_date=item.purchase_date,
            )

        holdings_df = p.holdings
        history_df = p.history(period=req.period)
        metrics = p.risk_metrics(period=req.period, risk_free_rate=req.risk_free_rate)

        # Serialize results safely
        serialized_holdings = df_to_json(holdings_df)
        
        serialized_history = []
        if not history_df.empty:
            serialized_history = df_to_json(history_df.reset_index())

        cleaned_metrics = {k: clean_json_val(v) for k, v in metrics.items()}

        payload = {
            "total_value": clean_json_val(p.value),
            "total_cost": clean_json_val(p.cost),
            "total_pnl": clean_json_val(p.pnl),
            "total_pnl_pct": clean_json_val(p.pnl_pct),
            "holdings": serialized_holdings,
            "performance_history": serialized_history,
            "risk_metrics": cleaned_metrics,
        }
        return compact_payload(payload)
    except Exception as exc:
        return {"error": f"Portfolio analysis failed: {exc}"}


@router.post("/rebalance")
@limiter.limit("10/minute")
def rebalance_portfolio(request: Request, response: Response, req: PortfolioRebalanceRequest):
    try:
        p = Portfolio()
        for item in req.holdings:
            p.add(
                symbol=item.symbol,
                shares=item.shares,
                cost=item.cost,
                asset_type=item.asset_type,
                purchase_date=item.purchase_date,
            )

        p.set_target_weights(req.target_weights)
        drift_df = p.drift()
        plan_df = p.rebalance_plan(threshold=req.threshold)

        payload = {
            "total_value": clean_json_val(p.value),
            "drift": df_to_json(drift_df),
            "rebalance_plan": df_to_json(plan_df),
        }
        return compact_payload(payload)
    except Exception as exc:
        return {"error": f"Portfolio rebalancing calculation failed: {exc}"}

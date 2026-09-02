from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from api_core.services.response import api_ok
from api_core.services.security import limiter

router = APIRouter(prefix="/calculator", tags=["calculator"])


@router.get("/compound")
@limiter.limit("60/minute")
def calculate_compound_interest(
    request: Request,
    response: Response,
    initial: float = Query(10000.0, ge=0, description="Baslangic anapara tutari (TRY)"),
    monthly: float = Query(2500.0, ge=0, description="Aylik duzenli eklenen tasarruf tutari (TRY)"),
    years: int = Query(5, ge=1, le=50, description="Yatirim vadesi (Yil)"),
    annual_rate: float = Query(40.0, ge=0, le=1000, description="Yillik beklenen yuzde getiri veya faiz orani"),
    envelope: bool = False,
):
    """Calculate compound interest and monthly savings growth over time with annual breakdown."""
    monthly_rate = (annual_rate / 100.0) / 12.0
    total_months = years * 12

    current_balance = initial
    total_invested = initial

    yearly_table = []
    
    for m in range(1, total_months + 1):
        current_balance += current_balance * monthly_rate
        current_balance += monthly
        total_invested += monthly

        if m % 12 == 0:
            year_num = m // 12
            yearly_table.append({
                "year": year_num,
                "total_invested": round(total_invested, 2),
                "portfolio_value": round(current_balance, 2),
                "total_profit": round(current_balance - total_invested, 2),
                "roi_percent": round(((current_balance - total_invested) / total_invested) * 100, 2) if total_invested > 0 else 0
            })

    total_profit = current_balance - total_invested
    roi_percent = (total_profit / total_invested * 100) if total_invested > 0 else 0

    result = {
        "inputs": {
            "initial_investment": initial,
            "monthly_contribution": monthly,
            "investment_years": years,
            "annual_rate_percent": annual_rate
        },
        "summary": {
            "total_invested": round(total_invested, 2),
            "final_portfolio_value": round(current_balance, 2),
            "total_profit": round(total_profit, 2),
            "roi_percent": round(roi_percent, 2),
            "multiplier": round(current_balance / total_invested, 2) if total_invested > 0 else 1.0
        },
        "yearly_schedule": yearly_table
    }

    return api_ok(result) if envelope else result

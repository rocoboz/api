from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("finansapi.warmer")

TR_TZ = timezone(timedelta(hours=3))

# Top active BIST symbols to keep warm during market hours
POPULAR_STOCKS = [
    "THYAO", "ASELS", "GARAN", "EREGL", "TUPRS",
    "KCHOL", "AKBNK", "ISCTR", "BIMAS", "SAHOL",
    "YKBNK", "PGSUS", "SISE", "FROTO", "PETKM"
]

# Top active TEFAS fund codes to keep warm during morning valuation hours
POPULAR_FUNDS = [
    "TI1", "AFT", "TTE", "YAY", "MAC",
    "NNF", "BIO", "AFA", "KHB", "GMR"
]


def is_bist_trading_hours() -> bool:
    """Return True if within BIST continuous auction trading window (Mon-Fri 09:55 - 18:15 TR time)."""
    now = datetime.now(TR_TZ)
    if now.weekday() >= 5:  # Saturday or Sunday
        return False
    minutes = now.hour * 60 + now.minute
    # 09:55 is 595, 18:15 is 1095
    return 595 <= minutes <= 1095


def is_tefas_valuation_hours() -> bool:
    """Return True if within morning TEFAS price declaration window (Mon-Fri 09:00 - 11:45 TR time)."""
    now = datetime.now(TR_TZ)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    # 09:00 is 540, 11:45 is 705
    return 540 <= minutes <= 705


async def _warm_market_overview():
    try:
        from api_core.routes.market import get_market_overview
        # Dummy request/response objects for FastAPI endpoint invocation
        class DummyObj:
            headers = {}
        await asyncio.to_thread(get_market_overview, DummyObj(), DummyObj())
        logger.info("[Warmer] Market overview warmed successfully.")
    except Exception as exc:
        logger.debug("[Warmer] Market overview warming error: %s", exc)


async def _warm_stock(symbol: str):
    try:
        from api_core.routes.stocks import get_stock
        class DummyObj:
            headers = {}
        await asyncio.to_thread(get_stock, DummyObj(), DummyObj(), symbol)
        logger.info("[Warmer] Stock %s warmed successfully.", symbol)
    except Exception as exc:
        logger.debug("[Warmer] Stock %s warming error: %s", symbol, exc)


async def _warm_funds():
    try:
        from api_core.routes.funds import get_top_funds, get_fund_detail
        class DummyObj:
            headers = {}

        # 1. Warm top funds
        await asyncio.to_thread(get_top_funds, DummyObj(), DummyObj(), "1y", None, 10, False)

        # 2. Warm popular individual funds
        for code in POPULAR_FUNDS[:5]:
            await asyncio.to_thread(get_fund_detail, DummyObj(), DummyObj(), code)
            await asyncio.sleep(1.5)  # Polite gap between TEFAS queries

        logger.info("[Warmer] TEFAS funds warmed successfully.")
    except Exception as exc:
        logger.debug("[Warmer] TEFAS funds warming error: %s", exc)


async def run_cache_warmer():
    """
    Continuous background task that proactively populates and refreshes
    cache based on BIST and TEFAS operating hours, ensuring 0ms latency for users
    while respecting polite upstream rate limits.
    """
    logger.info("Starting background proactive cache warmer...")
    # Initial pause to allow FastAPI startup to complete cleanly
    await asyncio.sleep(5)

    # Initial warm-up on server boot
    await _warm_market_overview()

    loop_count = 0
    while True:
        try:
            loop_count += 1
            now = datetime.now(TR_TZ)

            # 1. BIST Seansı (Hafta İçi 10:00 - 18:15): Her 60 saniyede bir piyasa özeti ve hisseler
            if is_bist_trading_hours():
                await _warm_market_overview()
                # Rotate through popular stocks, warming 3 stocks per loop to stay well under rate limits
                idx_start = (loop_count * 3) % len(POPULAR_STOCKS)
                batch = POPULAR_STOCKS[idx_start : idx_start + 3]
                for sym in batch:
                    await _warm_stock(sym)
                    await asyncio.sleep(1.5)  # Safe 1.5s gap between upstream queries
                sleep_duration = 50  # 50 seconds interval during trading
            else:
                # Seans dışı / Gece: Sadece piyasa özetini (döviz/altın) 10 dakikada bir güncelle
                if loop_count % 10 == 0:
                    await _warm_market_overview()
                sleep_duration = 60

            # 2. TEFAS Seansı (Hafta İçi 09:00 - 11:45): 15 dakikada bir fon fiyatlarını güncelle
            if is_tefas_valuation_hours():
                # Every ~15 minutes (approx every 15-18 loops of 50s)
                if loop_count % 15 == 1:
                    await _warm_funds()

            await asyncio.sleep(sleep_duration)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug("[Warmer] Main loop error: %s", exc)
            await asyncio.sleep(30)


def start_cache_warmer():
    """Start the background cache warmer in the running event loop."""
    asyncio.create_task(run_cache_warmer())

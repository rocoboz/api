from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from api_core.services.security import limiter

# Import data-fetching internals (bypassing rate-limited route wrappers)
from api_core.services.cache import get_cached_market, get_cached_realtime, get_cached_static
from api_core.services.enrichers import enrich_stock_row
from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json
from api_core.services.providers import Fund, Index, Ticker, get_kap_provider, market, technical
from api_core.services.response import api_ok

logger = logging.getLogger("finansapi.ai")

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


# ---------------------------------------------------------------------------
# Direct data helpers – these fetch data *without* going through the
# rate-limited FastAPI route wrappers so that AI tool calls don't consume the
# user's per-minute quota.
# ---------------------------------------------------------------------------

def _fetch_stock_details(symbol: str) -> dict:
    """Fetch basic quote details and KAP details for a BIST stock symbol."""
    symbol = symbol.upper()

    def fetch():
        tk = Ticker(symbol)
        try:
            info = dict(tk.fast_info) if hasattr(tk, "fast_info") else dict(tk.info)
        except Exception:
            info = dict(tk.info)

        try:
            kap = get_kap_provider()
            info["details"] = kap.get_company_details(symbol)
        except Exception:
            info["details"] = {}

        return compact_payload({"symbol": symbol, "data": info})

    try:
        return get_cached_market(f"STOCK_{symbol}", fetch)
    except Exception as exc:
        return {"error": str(exc)}


def _fetch_stock_history(symbol: str, period: str = "1mo", interval: str = "1d") -> Any:
    """Fetch historical OHLCV prices for a stock or fund."""
    symbol = symbol.upper()

    def fetch():
        obj = Ticker(symbol)
        df = obj.history(period=period, interval=interval)
        if df.empty:
            return {"error": "No data"}
        return df_to_json(df)

    try:
        return get_cached_realtime(f"HIST_{symbol}_{period}_{interval}", fetch)
    except Exception as exc:
        return {"error": str(exc)}


def _fetch_stock_recommendations(symbol: str) -> dict:
    symbol = symbol.upper()

    def fetch():
        tk = Ticker(symbol)
        try:
            targets = tk.analyst_price_targets
        except Exception:
            targets = {}
        try:
            summary = tk.recommendations_summary
        except Exception:
            summary = {}
        try:
            rec = tk.recommendations
        except Exception:
            rec = {}
        return compact_payload({
            "symbol": symbol,
            "targets": {k: clean_json_val(v) for k, v in targets.items()},
            "summary": {k: clean_json_val(v) for k, v in summary.items()},
            "overall": {k: clean_json_val(v) for k, v in rec.items()},
        })

    try:
        return get_cached_static(f"REC_{symbol}", fetch)
    except Exception as exc:
        return {"error": str(exc)}


def _fetch_major_holders(symbol: str) -> Any:
    symbol = symbol.upper()

    def fetch():
        tk = Ticker(symbol)
        df = tk.major_holders
        if df.empty:
            return []
        return df_to_json(df.reset_index())

    try:
        return get_cached_static(f"HOLDERS_{symbol}", fetch)
    except Exception as exc:
        return {"error": str(exc)}


def _fetch_etf_holders(symbol: str) -> Any:
    symbol = symbol.upper()

    def fetch():
        tk = Ticker(symbol)
        df = tk.etf_holders
        if df.empty:
            return []
        return df_to_json(df)

    try:
        return get_cached_static(f"ETFS_{symbol}", fetch)
    except Exception as exc:
        return {"error": str(exc)}


def _fetch_stock_calendar(symbol: str) -> dict:
    symbol = symbol.upper()

    def fetch():
        tk = Ticker(symbol)
        try:
            cal_df = tk.calendar
            cal = df_to_json(cal_df) if not cal_df.empty else []
        except Exception:
            cal = []
        try:
            earn_df = tk.earnings_dates
            earn = df_to_json(earn_df.reset_index()) if not earn_df.empty else []
        except Exception:
            earn = []
        return compact_payload({"symbol": symbol, "calendar": cal, "earnings_dates": earn})

    try:
        return get_cached_static(f"CAL_{symbol}", fetch)
    except Exception as exc:
        return {"error": str(exc)}


def _fetch_disclosures(symbol: str, limit: int = 15) -> Any:
    symbol = symbol.upper()

    def fetch():
        kap = get_kap_provider()
        return df_to_json(kap.get_disclosures(symbol, limit))

    try:
        return get_cached_market(f"DISC_{symbol}_{limit}", fetch)
    except Exception as exc:
        return {"error": str(exc)}


def _fetch_market_scan(universe: str = "XU030", condition: str = "", interval: str = "1d", limit: int = 100) -> Any:
    def fetch():
        try:
            from finans_core import scan
            univ = [s.strip().upper() for s in universe.split(",")] if "," in universe else universe.upper()
            df = scan(universe=univ, condition=condition, interval=interval, limit=limit)
            if df.empty:
                return []
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    try:
        return get_cached_realtime(f"SCAN_{universe}_{condition}_{interval}_{limit}", fetch)
    except Exception as exc:
        return {"error": str(exc)}


def _fetch_market_news() -> list:
    import urllib.request
    import xml.etree.ElementTree as ET

    def _rss(url: str, source_name: str, max_items: int = 10) -> list:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                xml_data = response.read()
            root = ET.fromstring(xml_data)
            items = []
            for item in root.findall(".//item")[:max_items]:
                title = item.find("title")
                link = item.find("link")
                pub_date = item.find("pubDate") or item.find("date")
                desc = item.find("description")
                items.append({
                    "source": source_name,
                    "title": title.text.strip() if title is not None and title.text else "",
                    "link": link.text.strip() if link is not None and link.text else "",
                    "date": pub_date.text.strip() if pub_date is not None and pub_date.text else "",
                    "summary": desc.text.strip() if desc is not None and desc.text else "",
                })
            return items
        except Exception:
            return []

    def fetch():
        news = []
        news.extend(_rss("https://www.bloomberght.com/rss", "Bloomberg HT", 10))
        news.extend(_rss("https://www.cnbc.com/id/10000664/device/rss/rss.html", "CNBC Finance", 10))
        return news

    try:
        return get_cached_realtime("NEWS_True_True", fetch)
    except Exception:
        return []


def _fetch_market_summary() -> dict:
    try:
        from tradingview_screener import Query as TvQuery
        _, breadth_df = TvQuery().set_markets("turkey").select("name", "change", "volume", "sector").get_scanner_data()
        if breadth_df.empty:
            return {"breadth": {"up": 0, "down": 0, "neutral": 0, "ratio": 0, "sentiment": "NEUTRAL"}}
        changes = breadth_df["change"].astype(float)
        up = int((changes > 0).sum())
        down = int((changes < 0).sum())
        neutral = int((changes == 0).sum())
        breadth = {
            "up": up, "down": down, "neutral": neutral,
            "ratio": round(up / down, 2) if down > 0 else up,
            "sentiment": "BULLISH" if up > down * 1.5 else ("BEARISH" if down > up * 1.5 else "NEUTRAL"),
        }
        return {"breadth": breadth}
    except Exception:
        return {"breadth": {"up": 0, "down": 0, "neutral": 0, "ratio": 0, "sentiment": "NEUTRAL"}}


def _fetch_fund_detail(code: str) -> dict:
    code = code.upper()

    def fetch():
        f = Fund(code)
        info = f.info
        if not info:
            return {"error": "Fund not found"}
        cleaned = {k: clean_json_val(v) for k, v in info.items()}
        return compact_payload(cleaned)

    try:
        return get_cached_static(f"FUND_DETAIL_{code}", fetch)
    except Exception as exc:
        return {"error": str(exc)}


def _fetch_fund_history(code: str, period: str = "1mo") -> Any:
    code = code.upper()

    def fetch():
        f = Fund(code)
        df = f.history(period=period)
        if df.empty:
            return []
        return df_to_json(df)

    try:
        return get_cached_realtime(f"FUND_HISTORY_{code}_{period}", fetch)
    except Exception as exc:
        return {"error": str(exc)}


def _fetch_fund_estimated_return(code: str) -> dict:
    code = code.upper()
    try:
        f = Fund(code)
        info = f.info or {}
        try:
            bist = Index("XU100").info.get("change_percent", 0) / 100
        except Exception:
            bist = 0
        return {
            "fund_code": code,
            "name": info.get("name"),
            "price": clean_json_val(info.get("price")),
            "daily_return": clean_json_val(info.get("daily_return")),
            "bist100_change_pct": round(bist * 100, 2),
        }
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Tool execution dispatcher
# ---------------------------------------------------------------------------

def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    """Execute local data functions based on model tool calls."""
    try:
        if name == "get_stock_details":
            return _fetch_stock_details(args.get("symbol", ""))
        elif name == "get_stock_history":
            return _fetch_stock_history(
                symbol=args.get("symbol", ""),
                period=args.get("period", "1mo"),
                interval=args.get("interval", "1d"),
            )
        elif name == "get_stock_recommendations":
            return _fetch_stock_recommendations(args.get("symbol", ""))
        elif name == "get_stock_holders":
            return _fetch_major_holders(args.get("symbol", ""))
        elif name == "get_stock_etfs":
            return _fetch_etf_holders(args.get("symbol", ""))
        elif name == "get_stock_calendar":
            return _fetch_stock_calendar(args.get("symbol", ""))
        elif name == "get_stock_news":
            return _fetch_disclosures(args.get("symbol", ""), limit=args.get("max_news", 10))
        elif name == "scan_market":
            return _fetch_market_scan(
                universe=args.get("universe", "XU030"),
                condition=args.get("condition", ""),
                interval=args.get("interval", "1d"),
                limit=args.get("limit", 50),
            )
        elif name == "get_market_news":
            return _fetch_market_news()
        elif name == "get_market_summary":
            return _fetch_market_summary()
        elif name == "get_fund_detail":
            return _fetch_fund_detail(args.get("code", ""))
        elif name == "get_fund_history":
            return _fetch_fund_history(args.get("code", ""), period=args.get("period", "1mo"))
        elif name == "get_fund_estimated_return":
            return _fetch_fund_estimated_return(args.get("code", ""))
        else:
            return {"error": f"Tool '{name}' not found."}
    except Exception as exc:
        return {"error": str(exc)}


def _safe_json_dumps(obj: Any) -> str:
    """Safely serialize objects to JSON, handling numpy/pandas types."""
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"error": "Serialization error"})


# ---------------------------------------------------------------------------
# Tool definitions for OpenAI-compatible function calling
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_details",
            "description": "Fetch basic quote details (price, change, volume, market cap) and KAP company details for a BIST stock symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "BIST stock symbol (e.g. THYAO, GARAN, ASELS)"}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_history",
            "description": "Fetch historical OHLCV price data for a stock. Returns dates, open, high, low, close, volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol (e.g. THYAO)"},
                    "period": {"type": "string", "description": "Time period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y", "default": "1mo"},
                    "interval": {"type": "string", "description": "Candle interval: 1d, 1h, 5m", "default": "1d"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_recommendations",
            "description": "Fetch analyst consensus recommendations, price targets (mean/high/low), and AL/SAT ratings for a stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_holders",
            "description": "Fetch major shareholders (ortaklık yapısı) for a stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_etfs",
            "description": "Fetch international ETFs that hold the specified stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_calendar",
            "description": "Fetch upcoming earnings dates, financial report calendar, and dividend calendar for a stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_market",
            "description": "Scan BIST index components using technical conditions. Example conditions: 'rsi < 30', 'close > sma_50', 'volume > 1000000'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "universe": {"type": "string", "description": "Index code (XU100, XU030) or comma-separated symbols", "default": "XU030"},
                    "condition": {"type": "string", "description": "Technical scan condition (e.g. 'rsi < 30', 'close > sma_50')"},
                    "interval": {"type": "string", "description": "Candle interval (1d, 1h)", "default": "1d"},
                    "limit": {"type": "integer", "description": "Max results to return", "default": 50},
                },
                "required": ["condition"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_news",
            "description": "Fetch the latest domestic (Bloomberg HT) and global (CNBC) financial news headlines.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_summary",
            "description": "Fetch BIST market breadth summary — how many stocks are up/down/flat and overall market sentiment.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_news",
            "description": "Fetch stock-specific KAP disclosures, announcements, and news for a BIST stock symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol (e.g. THYAO, TERA)"},
                    "max_news": {"type": "integer", "description": "Max number of disclosures to retrieve", "default": 10},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fund_detail",
            "description": "Fetch TEFAS fund details: name, category, price, daily return, fund size, investor count, risk value, and return history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "TEFAS fund code (e.g. TLY, IPJ, YAY)"}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fund_history",
            "description": "Fetch historical price/NAV data for a TEFAS fund.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "TEFAS fund code (e.g. TLY)"},
                    "period": {"type": "string", "description": "Time period: 1mo, 3mo, 6mo, 1y", "default": "1mo"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fund_estimated_return",
            "description": "Fetch estimated daily return breakdown for a TEFAS fund based on its portfolio allocation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "TEFAS fund code (e.g. TLY)"}
                },
                "required": ["code"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# System instruction for the orchestrator agent
# ---------------------------------------------------------------------------

SYSTEM_INSTRUCTION = """Sen Türk finans piyasalarında uzmanlaşmış bir **Çoklu Ajan Finansal Araştırma Koordinatörü**sün.

## Rol ve Görevlerin
Ekibinde dört uzman ajan bulunur:
1. **Teknik Analist**: RSI, MACD, MA crossover, destek/direnç, SuperTrend gibi göstergeleri analiz eder. (Not: Bu araçlar doğrudan fonksiyon olarak yoktur, fiyat geçmişi üzerinden yorum yapılmalıdır).
2. **Temel Analist**: F/K, PD/DD, bilanço, ortaklık yapısı, temettü ve değerleme analizi yapar.
3. **Makro & Haber Ajanı**: KAP bildirimleri, ekonomik takvim, faiz kararları ve haber sentimenti inceler.
4. **Veri Analisti**: İstatistiksel hesaplamalar ve karşılaştırmalı analizler yapar.

## Çalışma Prensipleri
- **Mutlaka veri araçlarını (tool) çağırarak gerçek ve güncel veri kullan.** Tahmini/hayali veri üretme.
- Kullanıcı bir hisse veya kripto sorduğunda en az `get_stock_details` ve `get_stock_history` araçlarını çağır.
- Kullanıcı fon sorduğunda `get_fund_detail` aracını çağır.
- Veri elde ettikten sonra analiz yap ve sentezle.
- Hangi ajanın hangi analizi yaptığını kısa belirt.

## Yanıt Formatı
- **Daima Türkçe** yanıt ver.
- **Zengin Markdown** kullan: başlıklar, tablolar, kalın metin, listeler, emoji.
- Türk hisseleri için fiyatları ₺ sembolü ile göster. Kripto veya yabancı paralar için fiyatta 'USD' veya 'Dolar' kullan. **Kesinlikle '$' (Dolar) sembolünü kullanma**, markdown LaTeX formatlama hatasına neden olur.
- Yüzdelik değişimleri renk ifadeleriyle belirt (📈 yeşil/yükseliş, 📉 kırmızı/düşüş).
- Analizin sonunda kısa bir **Özet Değerlendirme** yaz.

## Önemli Kurallar
- Python kodu yazma. Sadece metin tabanlı analiz yap.
- Araç (tool) çağrıları dışında harici kaynak referans verme.
- Belirsiz durumlarda varsayım yapma, kullanıcıya sor.
- Sembol kodlarını her zaman büyük harfle kullan (THYAO, GARAN, ASELS). Kripto paralar için '-USD' takısı ekle (örn. Bitcoin için BTC-USD)."""


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------

@router.post("/chat")
@limiter.limit("10/minute")
async def ai_chat(request: Request, response: Response, req: ChatRequest):
    # Resolve API key and provider
    custom_key = request.headers.get("X-AI-Key")
    custom_provider = request.headers.get("X-AI-Provider", "openai")
    custom_model = request.headers.get("X-AI-Model", "gpt-4.1-mini")

    openai_key = custom_key or os.getenv("OPENAI_API_KEY")

    if not openai_key:
        raise HTTPException(
            status_code=400,
            detail="AI Ajanlarının çalışabilmesi için geçerli bir API Anahtarı (API Key) tanımlanmış olmalıdır. Lütfen sağ üstteki ⚙️ Ayarlar menüsünden API anahtarınızı girin.",
        )

    # Determine base URL for different providers
    import openai

    base_url = None
    if custom_provider == "deepseek":
        base_url = "https://api.deepseek.com"
    elif custom_provider == "groq":
        base_url = "https://api.groq.com/openai/v1"
    elif custom_provider == "openrouter":
        base_url = "https://openrouter.ai/api/v1"
    elif custom_provider == "anthropic":
        # Anthropic is not OpenAI-compatible; use OpenRouter as a proxy
        base_url = "https://openrouter.ai/api/v1"
        # Prefix model name with anthropic/ if not already
        if not custom_model.startswith("anthropic/"):
            custom_model = f"anthropic/{custom_model}"
    elif custom_provider == "gemini":
        # Google Gemini via their OpenAI-compatible endpoint
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

    client = openai.OpenAI(api_key=openai_key, base_url=base_url)

    # Format messages
    api_messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
    api_messages.extend({"role": m.role, "content": m.content} for m in req.messages)

    try:
        completion = client.chat.completions.create(
            model=custom_model,
            messages=api_messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        message = completion.choices[0].message

        # If the model requested tool calls, execute them and get the final output
        if message.tool_calls:
            # Add assistant message containing the tool calls to history
            tool_calls_serialized = []
            for tc in message.tool_calls:
                tool_calls_serialized.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                })

            api_messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": tool_calls_serialized,
            })

            # Execute each tool call and append results
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                logger.info(f"AI tool call: {tc.function.name}({args})")
                result = execute_tool(tc.function.name, args)

                api_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": _safe_json_dumps(result),
                })

            # Request second completion with tool results
            second_completion = client.chat.completions.create(
                model=custom_model,
                messages=api_messages,
            )

            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": second_completion.choices[0].message.content or "",
                    }
                }]
            }

        # No tool calls — return the message directly
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": message.content or "",
                }
            }]
        }

    except openai.AuthenticationError:
        raise HTTPException(
            status_code=401,
            detail="API anahtarınız geçersiz. Lütfen Ayarlar menüsünden doğru anahtarı girin.",
        )
    except openai.RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="AI sağlayıcısının istek limiti aşıldı. Lütfen birkaç saniye bekleyip tekrar deneyin.",
        )
    except openai.BadRequestError as exc:
        error_msg = str(exc)
        if "model" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail=f"Seçilen model ({custom_model}) bu sağlayıcı tarafından desteklenmiyor. Lütfen Ayarlar menüsünden farklı bir model seçin.",
            )
        raise HTTPException(status_code=400, detail=f"AI sağlayıcısı hatası: {error_msg}")
    except Exception as exc:
        logger.exception("AI chat error")
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": f"⚠️ AI yanıtı alınırken bir hata oluştu: {exc}\n\nLütfen API anahtarınızı ve model seçiminizi kontrol edin.",
                }
            }]
        }

from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from api_core.services.cache import get_cached_market, get_cached_realtime, get_cached_static
from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json
from api_core.services.providers import FX, banks, metal_institutions
from api_core.services.response import api_ok
from api_core.services.security import limiter

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("/list")
@limiter.limit("20/minute")
def list_fx_info(request: Request, response: Response, envelope: bool = False):
    def fetch():
        try:
            return {
                "banks": banks(),
                "metal_institutions": metal_institutions(),
                "supported_assets_hint": [
                    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", 
                    "gram-altin", "22-ayar-bilezik", "18-ayar-altin", "14-ayar-altin",
                    "ceyrek-altin", "yarim-altin", "tam-altin", "cumhuriyet-altin", "ata-altin",
                    "gremse-altin", "resat-altin", "ons-altin", "gram-gumus", "gram-platin", 
                    "BRENT", "XAG-USD"
                ]
            }
        except Exception:
            return {"banks": [], "metal_institutions": []}

    data = get_cached_static("FX_INFO_LIST", fetch)
    return api_ok(data) if envelope else data


@router.get("/gold/all")
@limiter.limit("20/minute")
def get_all_gold_types(request: Request, response: Response):
    """Return all gold types (market-quoted and Darphane formula-derived) in a single matrix."""
    def fetch():
        try:
            gram_fx = FX("gram-altin").current or {}
            gram_price = float(gram_fx.get("last") or 0)

            usd_fx = FX("USD").current or {}
            usd_rate = float(usd_fx.get("last") or 0)

            ons_fx = FX("ons-altin").current or {}
            ons_try = float(ons_fx.get("last") or 0)
            ons_usd = round(ons_try / usd_rate, 2) if usd_rate > 0 else 0

            ceyrek_live = FX("ceyrek-altin").current or {}
            yarim_live = FX("yarim-altin").current or {}
            tam_live = FX("tam-altin").current or {}
            cumhuriyet_live = FX("cumhuriyet-altin").current or {}
            ata_live = FX("ata-altin").current or {}

            ceyrek_val = float(ceyrek_live.get("last") or (gram_price * 1.6065 * 1.03))
            yarim_val = float(yarim_live.get("last") or (gram_price * 3.2130 * 1.03))
            tam_val = float(tam_live.get("last") or (gram_price * 6.4260 * 1.03))
            cumhuriyet_val = float(cumhuriyet_live.get("last") or (gram_price * 6.6090 * 1.03))
            ata_val = float(ata_live.get("last") or (gram_price * 6.6090 * 1.035))

            gremse_val = round(ceyrek_val * 10, 2) if ceyrek_val else round(gram_price * 16.065 * 1.03, 2)
            resat_val = round(cumhuriyet_val * 1.015, 2) if cumhuriyet_val else round(gram_price * 6.600 * 1.04, 2)

            items = [
                {
                    "code": "gram-altin",
                    "name": "Gram Altın (24 Ayar Has)",
                    "purity": "24 Ayar (0.995)",
                    "total_weight_g": 1.0,
                    "pure_gold_g": 1.0,
                    "price": round(gram_price, 2),
                    "source": "live_market"
                },
                {
                    "code": "22-ayar-bilezik",
                    "name": "22 Ayar Bilezik (Gram)",
                    "purity": "22 Ayar (0.916)",
                    "total_weight_g": 1.0,
                    "pure_gold_g": 0.9166,
                    "price": round(gram_price * 0.9166, 2),
                    "source": "formula"
                },
                {
                    "code": "18-ayar-altin",
                    "name": "18 Ayar Altın (Gram)",
                    "purity": "18 Ayar (0.750)",
                    "total_weight_g": 1.0,
                    "pure_gold_g": 0.75,
                    "price": round(gram_price * 0.75, 2),
                    "source": "formula"
                },
                {
                    "code": "14-ayar-altin",
                    "name": "14 Ayar Altın (Gram)",
                    "purity": "14 Ayar (0.585)",
                    "total_weight_g": 1.0,
                    "pure_gold_g": 0.585,
                    "price": round(gram_price * 0.585, 2),
                    "source": "formula"
                },
                {
                    "code": "ceyrek-altin",
                    "name": "Çeyrek Altın (Yeni Tarihli)",
                    "purity": "22 Ayar (0.916)",
                    "total_weight_g": 1.754,
                    "pure_gold_g": 1.6065,
                    "price": round(ceyrek_val, 2),
                    "source": "live_market" if ceyrek_live.get("last") else "formula"
                },
                {
                    "code": "yarim-altin",
                    "name": "Yarım Altın",
                    "purity": "22 Ayar (0.916)",
                    "total_weight_g": 3.508,
                    "pure_gold_g": 3.213,
                    "price": round(yarim_val, 2),
                    "source": "live_market" if yarim_live.get("last") else "formula"
                },
                {
                    "code": "tam-altin",
                    "name": "Tam Altın (Ziynet)",
                    "purity": "22 Ayar (0.916)",
                    "total_weight_g": 7.016,
                    "pure_gold_g": 6.426,
                    "price": round(tam_val, 2),
                    "source": "live_market" if tam_live.get("last") else "formula"
                },
                {
                    "code": "cumhuriyet-altin",
                    "name": "Cumhuriyet Altını (Ata)",
                    "purity": "22 Ayar (0.916)",
                    "total_weight_g": 7.216,
                    "pure_gold_g": 6.609,
                    "price": round(cumhuriyet_val, 2),
                    "source": "live_market" if cumhuriyet_live.get("last") else "formula"
                },
                {
                    "code": "ata-altin",
                    "name": "Ata Altın",
                    "purity": "22 Ayar (0.916)",
                    "total_weight_g": 7.216,
                    "pure_gold_g": 6.609,
                    "price": round(ata_val, 2),
                    "source": "live_market" if ata_live.get("last") else "formula"
                },
                {
                    "code": "gremse-altin",
                    "name": "Gremse Altın (2.5'luk)",
                    "purity": "22 Ayar (0.916)",
                    "total_weight_g": 17.54,
                    "pure_gold_g": 16.065,
                    "price": round(gremse_val, 2),
                    "source": "formula"
                },
                {
                    "code": "resat-altin",
                    "name": "Reşat Altın",
                    "purity": "22 Ayar (0.916)",
                    "total_weight_g": 7.20,
                    "pure_gold_g": 6.60,
                    "price": round(resat_val, 2),
                    "source": "formula"
                },
                {
                    "code": "ons-altin",
                    "name": "Ons Altın (TRY)",
                    "purity": "24 Ayar (1.000)",
                    "total_weight_g": 31.1035,
                    "pure_gold_g": 31.1035,
                    "price": round(ons_try, 2),
                    "source": "live_market"
                },
                {
                    "code": "ons-altin-usd",
                    "name": "Ons Altın (USD)",
                    "purity": "24 Ayar (1.000)",
                    "total_weight_g": 31.1035,
                    "pure_gold_g": 31.1035,
                    "price": round(ons_usd, 2),
                    "source": "live_market"
                }
            ]

            return {
                "base_rates": {
                    "gram_altin_try": round(gram_price, 2),
                    "usd_try": round(usd_rate, 4),
                    "ons_altin_usd": round(ons_usd, 2),
                    "ons_altin_try": round(ons_try, 2),
                },
                "formula_note": "Tüm ayarlar ve basılı altınlar Darphane ve Damga Matbaası Genel Müdürlüğü resmi standartları ve saflık katsayılarına göre canlı piyasa verisiyle hesaplanmaktadır.",
                "gold_types": items
            }
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_realtime("FX_GOLD_ALL", fetch)


@router.get("/{asset}")
@limiter.limit("30/minute")
def get_fx_detail(request: Request, response: Response, asset: str):
    def fetch():
        try:
            fx = FX(asset)
            info = fx.current
            if info:
                return compact_payload({k: clean_json_val(v) for k, v in info.items()})

            # Check if requested asset is in derived gold types
            gold_matrix = get_all_gold_types(request, response)
            if isinstance(gold_matrix, dict) and "gold_types" in gold_matrix:
                for item in gold_matrix["gold_types"]:
                    if item["code"].lower() == asset.lower():
                        return {
                            "symbol": item["code"],
                            "name": item["name"],
                            "price": item["price"],
                            "last": item["price"],
                            "purity": item["purity"],
                            "pure_gold_g": item["pure_gold_g"],
                            "total_weight_g": item["total_weight_g"],
                            "source": item["source"]
                        }

            return {"error": f"Asset {asset} not found or unavailable"}
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_realtime(f"FX_{asset}", fetch)


@router.get("/{asset}/history")
@limiter.limit("30/minute")
def get_fx_history(request: Request, response: Response, asset: str, period: str = "1mo", interval: str = "1d"):
    def fetch():
        try:
            fx = FX(asset)
            df = fx.history(period=period, interval=interval)
            if df.empty:
                return {"error": "No historical data available"}
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_realtime(f"FX_HIST_{asset}_{period}_{interval}", fetch)


@router.get("/{asset}/bank-rates")
@limiter.limit("20/minute")
def get_fx_bank_rates(request: Request, response: Response, asset: str):
    def fetch():
        try:
            fx = FX(asset)
            df = fx.bank_rates
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"FX_BANKS_{asset}", fetch)


@router.get("/{asset}/bank-rate/{bank}")
@limiter.limit("20/minute")
def get_fx_bank_rate_detail(request: Request, response: Response, asset: str, bank: str):
    def fetch():
        try:
            fx = FX(asset)
            rate = fx.bank_rate(bank)
            return compact_payload({k: clean_json_val(v) for k, v in rate.items()})
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"FX_BANK_DETAIL_{asset}_{bank}", fetch)


@router.get("/{asset}/institution-rates")
@limiter.limit("20/minute")
def get_fx_institution_rates(request: Request, response: Response, asset: str):
    def fetch():
        try:
            fx = FX(asset)
            df = fx.institution_rates
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"FX_INSTITUTIONS_{asset}", fetch)


@router.get("/{asset}/institution-rate/{institution}")
@limiter.limit("20/minute")
def get_fx_institution_rate_detail(request: Request, response: Response, asset: str, institution: str):
    def fetch():
        try:
            fx = FX(asset)
            rate = fx.institution_rate(institution)
            return compact_payload({k: clean_json_val(v) for k, v in rate.items()})
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_market(f"FX_INSTITUTION_DETAIL_{asset}_{institution}", fetch)


@router.get("/{asset}/institution-history")
@limiter.limit("20/minute")
def get_fx_institution_history(request: Request, response: Response, asset: str, institution: str, period: str = "1mo"):
    def fetch():
        try:
            fx = FX(asset)
            df = fx.institution_history(institution=institution, period=period)
            if df.empty:
                return {"error": "No institution history data available"}
            return df_to_json(df)
        except Exception as exc:
            return {"error": str(exc)}

    return get_cached_realtime(f"FX_INST_HIST_{asset}_{institution}_{period}", fetch)

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response

from api_core.services.cache import get_cached_market, get_cached_realtime, get_cached_static
from api_core.services.normalizers import clean_json_val, compact_payload, df_to_json
from api_core.services.providers import FX, banks, metal_institutions
from api_core.services.response import api_ok
from api_core.services.security import limiter
from finans_core._providers.canlidoviz import get_canlidoviz_provider
from finans_core.assets import get_asset_spec, list_asset_specs, resolve_asset_code

router = APIRouter(prefix="/fx", tags=["fx"])

# Core products shown on the portfolio dashboard.  The long tail (Ziynet,
# Hamit, Beşibiryerde...) is still available through /fx/{asset}; it is kept out
# of the matrix so a cold start does not fan out to twenty upstream calls on a
# free Render instance.
GOLD_MATRIX_CODES = [
    "gram-altin",
    "has-altin",
    "22-ayar-bilezik",
    "18-ayar-altin",
    "14-ayar-altin",
    "ceyrek-altin",
    "yarim-altin",
    "tam-altin",
    "cumhuriyet-altin",
    "ata-altin",
    "resat-altin",
    "gremse-altin",
    "ons-altin",
]

MATRIX_CURRENCY_CODES = ["USD"]

# Minted products trade above their pure gold value because of minting and
# distribution costs.  These multipliers are used only when the live quote is
# unavailable; the response then reports source="formula".
FORMULA_PREMIUM = {
    "ceyrek-altin": 1.03,
    "yarim-altin": 1.03,
    "tam-altin": 1.03,
    "cumhuriyet-altin": 1.03,
    "ata-altin": 1.035,
    "resat-altin": 1.04,
    "gremse-altin": 1.03,
}

USD_NATIVE_CODES = {"ons-altin-usd", "xauusd", "ons-usd"}

_AYAR_BY_PURITY = {
    1.0: "24 Ayar",
    0.995: "24 Ayar",
    0.9166: "22 Ayar",
    0.916: "22 Ayar",
    0.75: "18 Ayar",
    0.585: "14 Ayar",
}


def _normalize_quote(value: str | None) -> str:
    quote = str(value or "TRY").strip().upper()
    if quote not in ("TRY", "SOURCE"):
        raise HTTPException(
            status_code=422, detail="quote yalnızca TRY veya SOURCE olabilir"
        )
    return quote


def _num(value: Any, digits: int = 4) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return round(number, digits)


def _purity_label(spec) -> str | None:
    if spec is None or spec.purity is None:
        return None
    for ratio, label in _AYAR_BY_PURITY.items():
        if abs(spec.purity - ratio) < 0.001:
            return f"{label} ({spec.purity:g})"
    return f"{spec.purity:g} saflık"


def _quote(asset: str, in_try: bool = True) -> dict[str, Any] | None:
    """Fetch one quote and swallow provider errors so batch calls can continue."""
    try:
        fx = FX(asset)
        info = fx.current_in_try if in_try else fx.current
    except Exception:
        return None
    if not info or info.get("error") or info.get("last") is None:
        return None
    return info


def _fetch_quotes(codes: list[str], in_try: bool = True) -> dict[str, dict[str, Any]]:
    """Fetch several quotes in parallel to stay inside the Render free plan."""
    unique_codes = list(dict.fromkeys(codes))
    if not unique_codes:
        return {}
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(unique_codes))) as executor:
        futures = {
            executor.submit(_quote, code, in_try): code for code in unique_codes
        }
        for future in as_completed(futures):
            code = futures[future]
            try:
                info = future.result()
            except Exception:
                info = None
            if info is not None:
                results[code] = info
    return results


def _quote_fields(info: dict[str, Any]) -> dict[str, Any]:
    updated_at = info.get("updated_at")
    if updated_at is None and info.get("update_time") is not None:
        update_time = info["update_time"]
        updated_at = (
            update_time.isoformat() if hasattr(update_time, "isoformat") else str(update_time)
        )

    fields: dict[str, Any] = {
        "price": _num(info.get("last")),
        "last": _num(info.get("last")),
        "open": _num(info.get("open")),
        "high": _num(info.get("high")),
        "low": _num(info.get("low")),
        "currency": str(info.get("currency") or "TRY").upper(),
        "unit_quantity": info.get("unit_quantity", 1),
        "price_type": info.get("price_type"),
        "source": info.get("source"),
        "source_item_id": info.get("source_item_id"),
        "updated_at": updated_at,
        "age_seconds": info.get("age_seconds"),
        "available": True,
    }
    if info.get("source_currency"):
        fields.update(
            {
                "source_currency": info.get("source_currency"),
                "source_price": _num(info.get("source_price")),
                "conversion_rate": _num(info.get("conversion_rate"), 6),
                "conversion_pair": info.get("conversion_pair"),
            }
        )
    return fields


def _spec_fields(spec) -> dict[str, Any]:
    if spec is None:
        return {}
    return {
        "name": spec.name,
        "kind": spec.kind,
        "unit": spec.unit,
        "quote_currency": spec.quote_currency,
        "purity": _purity_label(spec),
        "purity_ratio": spec.purity,
        "total_weight_g": spec.total_weight_g,
        "pure_gold_g": spec.pure_gold_g,
        "canlidoviz_id": spec.canlidoviz_id,
    }


def _formula_price(code: str, gram_try: float) -> float | None:
    """Fallback price derived from the gram gold quote.

    gram-altin is the price of one gram of 0.995 gold, so a product's pure
    gold content is divided by 0.995 before the minting premium is applied.
    """
    spec = get_asset_spec(code)
    gram_spec = get_asset_spec("gram-altin")
    if spec is None or spec.pure_gold_g is None or not gram_try:
        return None
    gram_purity = (gram_spec.purity if gram_spec and gram_spec.purity else 0.995)
    premium = FORMULA_PREMIUM.get(spec.code, 1.0)
    return round(gram_try * (spec.pure_gold_g / gram_purity) * premium, 2)


def _asset_payload(asset: str, quote: str = "TRY") -> dict[str, Any]:
    canonical = resolve_asset_code(asset)
    spec = get_asset_spec(canonical)
    quote_upper = quote.upper()

    payload: dict[str, Any] = {
        "code": canonical,
        "name": spec.name if spec else canonical,
        "kind": spec.kind if spec else "currency",
        "unit": spec.unit if spec else "unit",
        "unit_quantity": 1,
        "quote_currency": spec.quote_currency if spec else "TRY",
        "purity": _purity_label(spec),
        "purity_ratio": spec.purity if spec else None,
        "total_weight_g": spec.total_weight_g if spec else None,
        "pure_gold_g": spec.pure_gold_g if spec else None,
        "canlidoviz_id": spec.canlidoviz_id if spec else None,
    }

    info = _quote(canonical, in_try=(quote_upper != "SOURCE"))
    if info is not None:
        payload.update(_quote_fields(info))
        return compact_payload(payload)

    gram = _quote("gram-altin", in_try=True) if quote_upper != "SOURCE" else None
    gram_price = float(gram.get("last") or 0) if gram else 0.0
    fallback = _formula_price(canonical, gram_price)
    if fallback is not None:
        payload.update(
            {
                "price": fallback,
                "last": fallback,
                "currency": "TRY",
                "available": True,
                "source": "formula",
                "price_type": "derived",
                "derived_from": "gram-altin",
            }
        )
        return compact_payload(payload)

    payload.update(
        {
            "available": False,
            "error": f"Fiyat alınamadı: {canonical}",
        }
    )
    return compact_payload(payload)


def _is_known_asset(asset: str) -> bool:
    if get_asset_spec(asset) is not None:
        return True
    return resolve_asset_code(asset).upper() in get_canlidoviz_provider().CURRENCY_IDS


@router.get("/list")
@limiter.limit("30/minute")
def list_fx_info(request: Request, response: Response, envelope: bool = False):
    def fetch():
        try:
            return {
                "banks": banks(),
                "metal_institutions": metal_institutions(),
                "supported_assets_hint": [
                    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD",
                    *[spec.code for spec in list_asset_specs()],
                ],
            }
        except Exception:
            return {"banks": [], "metal_institutions": []}

    data = get_cached_static("FX_INFO_LIST", fetch)
    return api_ok(data) if envelope else data


@router.get("/assets")
@limiter.limit("60/minute")
def list_fx_assets(request: Request, response: Response, kind: str | None = None):
    """Static catalogue of currencies, gold, silver, platinum and energy assets."""

    def fetch():
        assets: list[dict[str, Any]] = [
            {
                "code": code,
                "name": code,
                "kind": "currency",
                "unit": "unit",
                "quote_currency": "TRY",
                "canlidoviz_id": item_id,
            }
            for code, item_id in sorted(get_canlidoviz_provider().CURRENCY_IDS.items())
        ]
        for spec in list_asset_specs():
            assets.append(
                {
                    "code": spec.code,
                    "name": spec.name,
                    "kind": spec.kind,
                    "unit": spec.unit,
                    "quote_currency": spec.quote_currency,
                    "aliases": list(spec.aliases),
                    **_spec_fields(spec),
                }
            )
        if kind:
            wanted = kind.strip().lower()
            assets = [item for item in assets if item["kind"] == wanted]
        return {
            "base_currency": "TRY",
            "count": len(assets),
            "assets": assets,
        }

    return get_cached_static(f"FX_ASSET_CATALOG_{kind or 'all'}", fetch)


def _get_all_gold_types_payload():
    codes = list(dict.fromkeys(GOLD_MATRIX_CODES + MATRIX_CURRENCY_CODES))
    quotes = _fetch_quotes(codes, in_try=True)

    gram_info = quotes.get("gram-altin") or {}
    gram_price = float(gram_info.get("last") or 0)
    usd_rate = float((quotes.get("USD") or {}).get("last") or 0)
    ons_info = quotes.get("ons-altin") or {}
    ons_try = float(ons_info.get("last") or 0)
    ons_usd = float(ons_info.get("source_price") or 0)

    gold_types: list[dict[str, Any]] = []
    for code in GOLD_MATRIX_CODES:
        spec = get_asset_spec(code)
        item: dict[str, Any] = {"code": code, **_spec_fields(spec)}
        info = quotes.get(code)
        if info is not None:
            item.update(_quote_fields(info))
        else:
            fallback = _formula_price(code, gram_price)
            if fallback is None:
                item.update(
                    {
                        "available": False,
                        "error": f"Fiyat alınamadı: {code}",
                    }
                )
            else:
                item.update(
                    {
                        "price": fallback,
                        "last": fallback,
                        "currency": "TRY",
                        "available": True,
                        "source": "formula",
                        "price_type": "derived",
                        "derived_from": "gram-altin",
                    }
                )
        gold_types.append(compact_payload(item))

    if ons_usd > 0:
        updated_at = ons_info.get("updated_at")
        gold_types.append(
            compact_payload(
                {
                    "code": "ons-altin-usd",
                    "name": "Ons Altın (ABD Doları)",
                    "kind": "gold",
                    "unit": "ounce",
                    "quote_currency": "USD",
                    "currency": "USD",
                    "price": round(ons_usd, 2),
                    "last": round(ons_usd, 2),
                    "available": True,
                    "source": ons_info.get("source"),
                    "price_type": ons_info.get("price_type"),
                    "derived_from": "ons-altin",
                    "updated_at": updated_at,
                }
            )
        )

    return compact_payload(
        {
            "base_rates": {
                "gram_altin_try": round(gram_price, 4),
                "usd_try": round(usd_rate, 4),
                "ons_altin_usd": round(ons_usd, 2),
                "ons_altin_try": round(ons_try, 2),
            },
            "formula_note": (
                "Fiyatlar önce canlı piyasa kotasyonundan alınır. Kotasyon "
                "alınamazsa gram altın fiyatı ve Darphane saflık katsayılarıyla "
                "hesaplanır ve source alanı 'formula' olarak işaretlenir."
            ),
            "gold_types": gold_types,
        }
    )


@router.get("/gold/all")
@limiter.limit("30/minute")
def get_all_gold_types(request: Request, response: Response):
    """Return all core gold products in Turkish lira plus the USD ounce quote."""
    return get_cached_realtime("FX_GOLD_ALL", _get_all_gold_types_payload)


@router.get("/quotes")
@limiter.limit("60/minute")
def get_fx_quotes(
    request: Request,
    response: Response,
    symbols: str = Query(..., description="Comma separated asset codes, maximum 30"),
    quote: str = Query("TRY", description="TRY or SOURCE"),
):
    """Batch quote endpoint used by the portfolio screen to avoid N requests."""
    quote_upper = _normalize_quote(quote)
    codes = [item.strip() for item in symbols.split(",") if item.strip()]
    codes = list(dict.fromkeys(codes))[:30]
    if not codes:
        raise HTTPException(status_code=400, detail="symbols parametresi boş olamaz")

    def fetch():
        quotes = [_asset_payload(code, quote=quote_upper) for code in codes]
        return {
            "base_currency": quote_upper,
            "count": len(quotes),
            "quotes": quotes,
        }

    cache_key = f"FX_QUOTES_{quote_upper}_{','.join(sorted(codes))}"
    return get_cached_realtime(cache_key, fetch)


def _get_asset_price_in_try(asset_name: str) -> float | None:
    sym = asset_name.strip()
    if sym.upper() in ("TRY", "TL"):
        return 1.0

    resolved = resolve_asset_code(sym)
    info = _quote(resolved, in_try=True)
    if info is not None and info.get("last"):
        # JPY is quoted per 100 yen; conversions work per single unit.
        unit_quantity = float(info.get("unit_quantity") or 1)
        return float(info["last"]) / unit_quantity

    gram = _quote("gram-altin", in_try=True)
    gram_price = float(gram.get("last") or 0) if gram else 0.0
    return _formula_price(resolved, gram_price)


@router.get("/convert")
@limiter.limit("60/minute")
def convert_fx(
    request: Request,
    response: Response,
    from_asset: str = Query(..., alias="from", description="Source currency or gold code (e.g. USD, EUR, gram-altin, ceyrek-altin, TRY)"),
    to_asset: str = Query("TRY", alias="to", description="Target currency or gold code (e.g. TRY, USD, EUR, gram-altin)"),
    amount: float = Query(1.0, gt=0, description="Amount to convert"),
):
    """Convert amounts between live currencies, precious metals (gold/silver), and Turkish Lira."""
    from_asset = from_asset.strip()
    to_asset = to_asset.strip()

    def fetch():
        rate_from = _get_asset_price_in_try(from_asset)
        rate_to = _get_asset_price_in_try(to_asset)

        if rate_from is None:
            return {"error": f"Unsupported or unavailable source asset: '{from_asset}'"}
        if rate_to is None:
            return {"error": f"Unsupported or unavailable target asset: '{to_asset}'"}
        if rate_to <= 0:
            return {"error": f"Invalid conversion rate for target asset: '{to_asset}'"}

        total_in_try = amount * rate_from
        converted_amount = total_in_try / rate_to
        unit_rate = rate_from / rate_to

        return {
            "from": resolve_asset_code(from_asset).upper(),
            "to": resolve_asset_code(to_asset).upper(),
            "amount": amount,
            "rate": round(unit_rate, 6),
            "result": round(converted_amount, 4),
            "value_in_try": round(total_in_try, 2),
            "from_rate_try": round(rate_from, 4),
            "to_rate_try": round(rate_to, 4),
        }

    return get_cached_realtime(
        f"FX_CONV_{from_asset}_{to_asset}_{amount}", fetch
    )


@router.get("/{asset}")
@limiter.limit("60/minute")
def get_fx_detail(
    request: Request,
    response: Response,
    asset: str,
    quote: str | None = Query(None, description="TRY or SOURCE"),
):
    """Return a single quote without building the whole gold matrix."""
    raw = asset.strip().lower()
    default_quote = "SOURCE" if raw in USD_NATIVE_CODES else "TRY"
    effective_quote = _normalize_quote(quote or default_quote)

    def fetch():
        payload = _asset_payload(asset, quote=effective_quote)
        if payload.get("error"):
            if not _is_known_asset(asset):
                raise HTTPException(status_code=404, detail=f"Bilinmeyen varlık: {asset}")
            raise HTTPException(status_code=503, detail=payload["error"])
        return payload

    return get_cached_realtime(f"FX_{effective_quote}_{asset}", fetch)


@router.get("/{asset}/history")
@limiter.limit("60/minute")
def get_fx_history(
    request: Request,
    response: Response,
    asset: str,
    period: str = "1mo",
    interval: str = "1d",
    quote: str = Query("TRY", description="TRY or SOURCE"),
    envelope: bool = False,
):
    """Historical OHLC data with dates, source and currency metadata."""
    quote_upper = _normalize_quote(quote)

    def fetch():
        try:
            fx = FX(asset)
            df = (
                fx.history_in_try(period=period, interval=interval)
                if quote_upper == "TRY"
                else fx.history(period=period, interval=interval)
            )
        except Exception as exc:
            if not _is_known_asset(asset):
                raise HTTPException(status_code=404, detail=f"Bilinmeyen varlık: {asset}") from exc
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        if df.empty:
            raise HTTPException(status_code=404, detail="Geçmiş veri bulunamadı")

        rows = df_to_json(df)
        if not envelope:
            return rows

        attrs = dict(df.attrs or {})
        return {
            "asset": resolve_asset_code(asset),
            "period": period,
            "interval": interval,
            "currency": attrs.get("currency"),
            "source": attrs.get("source"),
            "source_currency": attrs.get("source_currency"),
            "price_type": attrs.get("price_type"),
            "unit": attrs.get("unit"),
            "unit_quantity": attrs.get("unit_quantity", 1),
            "conversion_pair": attrs.get("conversion_pair"),
            "count": len(rows),
            "data": rows,
        }

    return get_cached_realtime(f"FX_HIST_{asset}_{period}_{interval}_{quote_upper}", fetch)


@router.get("/{asset}/bank-rates")
@limiter.limit("30/minute")
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
@limiter.limit("30/minute")
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
@limiter.limit("30/minute")
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
@limiter.limit("30/minute")
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
@limiter.limit("30/minute")
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

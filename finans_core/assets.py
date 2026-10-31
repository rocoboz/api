"""Canonical asset metadata for Turkish gold, silver and platinum products.

The identifiers in this module are verified against the canlidoviz.com detail
pages.  They are deliberately kept in one place because the same asset code is
used by the provider, the HTTP routes and the portfolio calculator.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AssetSpec:
    code: str
    name: str
    kind: str
    quote_currency: str
    unit: str
    canlidoviz_id: int | None = None
    purity: float | None = None
    total_weight_g: float | None = None
    pure_gold_g: float | None = None
    aliases: tuple[str, ...] = ()
    derived_from: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


ASSET_SPECS: dict[str, AssetSpec] = {
    "gram-altin": AssetSpec(
        code="gram-altin",
        name="Gram Altın (24 Ayar Has)",
        kind="gold",
        quote_currency="TRY",
        unit="gram",
        canlidoviz_id=32,
        purity=0.995,
        total_weight_g=1.0,
        pure_gold_g=0.995,
        aliases=("gram", "altin"),
    ),
    "has-altin": AssetSpec(
        code="has-altin",
        name="Has Altın (24 Ayar)",
        kind="gold",
        quote_currency="TRY",
        unit="gram",
        canlidoviz_id=1179,
        purity=0.995,
        total_weight_g=1.0,
        pure_gold_g=0.995,
        aliases=("kulce-altin", "kulce"),
    ),
    "ceyrek-altin": AssetSpec(
        code="ceyrek-altin",
        name="Çeyrek Altın",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=11,
        purity=0.916,
        total_weight_g=1.754,
        pure_gold_g=1.6065,
        aliases=("ceyrek",),
    ),
    "yarim-altin": AssetSpec(
        code="yarim-altin",
        name="Yarım Altın",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=47,
        purity=0.916,
        total_weight_g=3.508,
        pure_gold_g=3.213,
        aliases=("yarim",),
    ),
    "tam-altin": AssetSpec(
        code="tam-altin",
        name="Tam Altın",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=14,
        purity=0.916,
        total_weight_g=7.016,
        pure_gold_g=6.426,
        aliases=("tam",),
    ),
    "cumhuriyet-altin": AssetSpec(
        code="cumhuriyet-altin",
        name="Cumhuriyet Altını",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=27,
        purity=0.916,
        total_weight_g=7.216,
        pure_gold_g=6.609,
        aliases=("cumhuriyet",),
    ),
    "ata-altin": AssetSpec(
        code="ata-altin",
        name="Ata Altın",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=58,
        purity=0.916,
        total_weight_g=7.216,
        pure_gold_g=6.609,
        aliases=("ata",),
    ),
    "resat-altin": AssetSpec(
        code="resat-altin",
        name="Reşat Altın",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=43,
        purity=0.916,
        total_weight_g=7.20,
        pure_gold_g=6.60,
        aliases=("resat", "resat-lira-altin"),
    ),
    "gremse-altin": AssetSpec(
        code="gremse-altin",
        name="Gremse Altın",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=15,
        purity=0.916,
        total_weight_g=17.54,
        pure_gold_g=16.065,
        aliases=("gremse",),
    ),
    "22-ayar-bilezik": AssetSpec(
        code="22-ayar-bilezik",
        name="22 Ayar Bilezik (Gram)",
        kind="gold",
        quote_currency="TRY",
        unit="gram",
        canlidoviz_id=18,
        purity=0.9166,
        total_weight_g=1.0,
        pure_gold_g=0.9166,
        aliases=("22-ayar-altin", "22-ayar", "bilezik"),
    ),
    "18-ayar-altin": AssetSpec(
        code="18-ayar-altin",
        name="18 Ayar Altın (Gram)",
        kind="gold",
        quote_currency="TRY",
        unit="gram",
        canlidoviz_id=55,
        purity=0.75,
        total_weight_g=1.0,
        pure_gold_g=0.75,
    ),
    "14-ayar-altin": AssetSpec(
        code="14-ayar-altin",
        name="14 Ayar Altın (Gram)",
        kind="gold",
        quote_currency="TRY",
        unit="gram",
        canlidoviz_id=16,
        purity=0.585,
        total_weight_g=1.0,
        pure_gold_g=0.585,
    ),
    "ons-altin": AssetSpec(
        code="ons-altin",
        name="Ons Altın",
        kind="gold",
        quote_currency="USD",
        unit="ounce",
        canlidoviz_id=12,
        purity=1.0,
        total_weight_g=31.1035,
        pure_gold_g=31.1035,
        aliases=("ons", "ons-altin-usd", "xau", "xauusd"),
    ),
    "gram-gumus": AssetSpec(
        code="gram-gumus",
        name="Gram Gümüş",
        kind="silver",
        quote_currency="TRY",
        unit="gram",
        canlidoviz_id=20,
        purity=0.925,
        total_weight_g=1.0,
        pure_gold_g=None,
        aliases=("gumus",),
    ),
    "gram-platin": AssetSpec(
        code="gram-platin",
        name="Gram Platin",
        kind="platinum",
        quote_currency="TRY",
        unit="gram",
        canlidoviz_id=1012,
        purity=0.95,
        total_weight_g=1.0,
        pure_gold_g=None,
    ),
    "ikibucuk-altin": AssetSpec(
        code="ikibucuk-altin",
        name="İkibuçuk Altın",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=81,
        purity=0.916,
    ),
    "besli-altin": AssetSpec(
        code="besli-altin",
        name="Beşli Altın",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=28,
        purity=0.916,
    ),
    "ziynet-altin": AssetSpec(
        code="ziynet-altin",
        name="Ziynet Altın",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=1180,
        purity=0.916,
    ),
    "hamit-altin": AssetSpec(
        code="hamit-altin",
        name="Hamit Altın",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=782,
        purity=0.916,
    ),
    "resat-besibiryerde": AssetSpec(
        code="resat-besibiryerde",
        name="Reşat Beşibiryerde",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=1247,
        purity=0.916,
    ),
    "resat-ikibucuk-altin": AssetSpec(
        code="resat-ikibucuk-altin",
        name="Reşat İkibuçuk Altın",
        kind="gold",
        quote_currency="TRY",
        unit="piece",
        canlidoviz_id=1248,
        purity=0.916,
    ),
    "XAG-USD": AssetSpec(
        code="XAG-USD",
        name="Gümüş Ons (Amerikan Doları)",
        kind="silver",
        quote_currency="USD",
        unit="ounce",
        canlidoviz_id=267,
    ),
    "XPT-USD": AssetSpec(
        code="XPT-USD",
        name="Platin Spot (Amerikan Doları)",
        kind="platinum",
        quote_currency="USD",
        unit="ounce",
        canlidoviz_id=268,
    ),
    "XPD-USD": AssetSpec(
        code="XPD-USD",
        name="Paladyum Spot (Amerikan Doları)",
        kind="palladium",
        quote_currency="USD",
        unit="ounce",
        canlidoviz_id=269,
    ),
    "BRENT": AssetSpec(
        code="BRENT",
        name="Brent Petrol",
        kind="energy",
        quote_currency="USD",
        unit="barrel",
        canlidoviz_id=266,
    ),
}


ALIASES: dict[str, str] = {}
_LOWER_TO_CODE: dict[str, str] = {}
for _code, _spec in ASSET_SPECS.items():
    ALIASES[_code.lower()] = _code
    _LOWER_TO_CODE[_code.lower()] = _code
    for _alias in _spec.aliases:
        ALIASES[_alias.lower()] = _code


def resolve_asset_code(code: str) -> str:
    """Resolve a user supplied code or alias to its canonical asset code.

    Currency codes are case-insensitive and are returned in upper case so that
    the existing canlidoviz currency identifiers keep working.
    """
    raw = str(code or "").strip()
    if not raw:
        return raw
    key = raw.lower()
    resolved = ALIASES.get(key) or _LOWER_TO_CODE.get(key)
    if resolved:
        return resolved
    return raw.upper()


def get_asset_spec(code: str) -> AssetSpec | None:
    return ASSET_SPECS.get(resolve_asset_code(code))


def list_asset_specs(kind: str | None = None) -> list[AssetSpec]:
    specs = sorted(ASSET_SPECS.values(), key=lambda item: item.code)
    if kind is None:
        return specs
    return [item for item in specs if item.kind == kind]

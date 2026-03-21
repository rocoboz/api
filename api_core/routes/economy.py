from fastapi import APIRouter

from api_core.services.cache import get_cached_market, get_cached_static
from api_core.services.normalizers import df_to_json
from api_core.services.providers import EconomicCalendar, Inflation, TCMB, VIOP, tax

router = APIRouter(tags=["economy"])


@router.get("/market/economy/rates")
def get_tcmb_rates():
    def fetch():
        try:
            return df_to_json(TCMB().rates)
        except Exception as exc:
            return {"error": f"TCMB Provider Error: {exc}"}

    return get_cached_static("TCMB_RATES", fetch)


@router.get("/market/economy/calendar")
def get_economic_calendar(scope: str = "today"):
    def fetch():
        cal = EconomicCalendar()
        if scope == "week":
            df = cal.this_week()
        elif scope == "month":
            df = cal.this_month()
        else:
            df = cal.today()
        return df_to_json(df)

    return get_cached_market(f"CALENDAR_{scope}", fetch)


@router.get("/viop/list")
def viop_list(category: str = "all"):
    def fetch():
        v = VIOP()
        if category == "stock":
            return df_to_json(v.stock_futures)
        return df_to_json(v.futures)

    return get_cached_market(f"VIOP_LIST_{category}", fetch)


@router.get("/market/economy/inflation")
def inflation_data():
    def fetch():
        inf = Inflation()
        return {"tufe": inf.latest("tufe"), "ufe": inf.latest("ufe")}

    return get_cached_static("INFLATION", fetch)


@router.get("/market/tax")
def tax_table():
    return get_cached_static("TAX_TABLE", lambda: df_to_json(tax.withholding_tax_table()))

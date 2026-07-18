from pydantic import BaseModel


class SupportedCurrenciesOut(BaseModel):
    currencies: dict[str, str]


class PrefetchIn(BaseModel):
    from_currency: str  # 3-char ISO 4217
    to_currency: str
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD


class PrefetchOut(BaseModel):
    from_currency: str
    to_currency: str
    start_date: str
    end_date: str
    fetched: int
    skipped_cached: int
    unavailable: int

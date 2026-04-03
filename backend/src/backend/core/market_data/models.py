from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

MarketCode = Literal["tw", "us"]
Timeframe = Literal["1d"]


class Quote(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    symbol: str
    market: MarketCode
    name: str | None = None
    price: float
    source: str
    timestamp: datetime | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: int | None = None


class Bar(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    symbol: str
    market: MarketCode
    timeframe: Timeframe = "1d"
    bar_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None
    adjusted: bool = True
    source: str


class ChipsDaily(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    symbol: str
    market: Literal["tw"] = "tw"
    trade_date: date
    source: str
    foreign_net: int | None = None
    trust_net: int | None = None
    dealer_net: int | None = None
    margin_balance: int | None = None

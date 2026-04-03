from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class MarketSnapshot:
    market_id: str
    slug: str
    question: str
    yes_price: float
    no_price: float
    volume_24h: float
    liquidity: float
    one_day_price_change: float
    best_bid: float | None
    best_ask: float | None
    end_date: str | None
    days_to_resolution: int | None

    @property
    def spread(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return max(0.0, self.best_ask - self.best_bid)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["spread"] = self.spread
        return data


@dataclass(slots=True)
class TradeDecision:
    action: str
    market_id: str
    slug: str
    question: str
    market_yes: float
    model_yes: float
    edge: float
    paper_size: float
    shares: float
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)

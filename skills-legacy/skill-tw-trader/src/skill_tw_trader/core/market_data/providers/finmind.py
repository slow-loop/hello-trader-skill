from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
from FinMind.data import DataLoader

from skill_tw_trader.core.market_data.models import ChipsDaily
from skill_tw_trader.core.market_data.symbols import detect_market, normalize_symbol, strip_suffix

_INVESTOR_FIELDS = {
    "Foreign_Investor": "foreign_net",
    "Investment_Trust": "trust_net",
    "Dealer_self": "dealer_net",
}

_loader: DataLoader | None = None


def fetch_chips(symbol: str, lookback_days: int = 180) -> list[ChipsDaily]:
    normalized = normalize_symbol(symbol)
    if detect_market(normalized) != "tw":
        raise ValueError("chips only supports tw symbols")

    stock_id = strip_suffix(normalized)
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days + 10)
    loader = _get_loader()

    frames: list[pd.DataFrame] = []
    investor_df = loader.taiwan_stock_institutional_investors(
        stock_id=stock_id,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )
    if not investor_df.empty:
        investor_df = investor_df[investor_df["name"].isin(_INVESTOR_FIELDS)].copy()
        if not investor_df.empty:
            investor_df["net"] = investor_df["buy"] - investor_df["sell"]
            investor_df["field"] = investor_df["name"].map(_INVESTOR_FIELDS)
            investor_pivot = (
                investor_df.pivot_table(index="date", columns="field", values="net", aggfunc="last")
                .reset_index()
                .rename(columns={"date": "trade_date"})
            )
            frames.append(investor_pivot)

    margin_df = loader.taiwan_stock_margin_purchase_short_sale(
        stock_id=stock_id,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )
    if not margin_df.empty and "MarginPurchaseTodayBalance" in margin_df.columns:
        margin_df = (
            margin_df[["date", "MarginPurchaseTodayBalance"]]
            .drop_duplicates(subset=["date"], keep="last")
            .rename(columns={"date": "trade_date", "MarginPurchaseTodayBalance": "margin_balance"})
        )
        frames.append(margin_df)

    if not frames:
        return []

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="trade_date", how="outer")

    merged["trade_date"] = pd.to_datetime(merged["trade_date"]).dt.date
    merged = merged.sort_values("trade_date")

    rows: list[ChipsDaily] = []
    for row in merged.to_dict("records"):
        rows.append(
            ChipsDaily(
                symbol=normalized,
                trade_date=row["trade_date"],
                source="finmind",
                foreign_net=_maybe_int(row.get("foreign_net")),
                trust_net=_maybe_int(row.get("trust_net")),
                dealer_net=_maybe_int(row.get("dealer_net")),
                margin_balance=_maybe_int(row.get("margin_balance")),
            )
        )
    return rows


def _get_loader() -> DataLoader:
    global _loader
    if _loader is not None:
        return _loader

    api_key = os.environ.get("FINMIND_API_KEY")
    if not api_key:
        raise ValueError("FINMIND_API_KEY environment variable is not set")

    loader = DataLoader()
    loader.login_by_token(api_token=api_key)
    _loader = loader
    return _loader


def _maybe_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)

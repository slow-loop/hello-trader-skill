from __future__ import annotations

from datetime import date, datetime, timedelta

import httpx
import pandas as pd
import pandas_ta as ta
import yaml

from skill_tw_trader.core.market_calendar import get_twse_market_session, get_twse_market_status
from skill_tw_trader.core.market_data import get_bars, get_chips, get_quote
from skill_tw_trader.core.market_data.symbols import normalize_symbol, strip_suffix
from skill_tw_trader.core.account_paths import MARKET_SNAPSHOTS_DIR
from skill_tw_trader.core.technical_engine import (
    build_technical_analysis,
    get_expression_definitions,
    get_indicator_definitions,
    load_analysis_config,
)

MARKET_SNAPSHOTS_KEEP_DAYS = 7

NEWS_CATEGORIES = {
    "tw_stock": "tw_stock",
    "wd_stock": "wd_stock",
    "headlines": "headline",
}
CNYES_API = "https://news.cnyes.com/api/v3/news/category/{cat}?limit={limit}"
CNYES_URL_BASE = "https://news.cnyes.com/news/id/{news_id}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; tw-trader-bot/1.0)"}


def build_market_report(symbols: list[str] | None = None) -> dict:
    normalized_symbols = [normalize_symbol(symbol) for symbol in symbols or []]
    if not normalized_symbols:
        return build_overview()

    overview = build_overview()
    all_news = _fetch_news(categories=["headlines", "tw_stock"], limit=30)
    stocks: list[dict] = []
    for symbol in normalized_symbols:
        stocks.append(build_stock_analysis(symbol, all_news=all_news))

    return {
        "date": overview["date"],
        "session": overview["session"],
        "market": overview["market"],
        "headlines": overview.get("headlines", [])[:5],
        "stocks": stocks,
    }


def build_overview() -> dict:
    market_status = get_twse_market_status()
    news = _fetch_news(categories=["headlines", "tw_stock"], limit=15)

    return {
        "date": date.today().isoformat(),
        "session": get_twse_market_session(),
        "market": {
            **_get_index_data(),
            "trend": _classify_index_trend(),
            "is_open": market_status["is_open"],
            "reason": market_status["reason"],
        },
        "headlines": _public_news_items(news),
    }


def build_stock_analysis(symbol: str, all_news: list[dict] | None = None) -> dict:
    normalized = normalize_symbol(symbol)
    config = load_analysis_config()
    quote = get_quote(normalized)
    df = get_history_dataframe(normalized, days=120)
    analysis = build_technical_analysis(
        df,
        indicators=get_indicator_definitions(config),
        expressions=get_expression_definitions(config),
    )

    result = {
        "symbol": normalized,
        "quote": {
            "name": quote.name,
            "price": quote.price,
            "change": quote.change,
            "change_pct": quote.change_pct,
            "source": quote.source,
        },
        "metrics": {
            k: (round(v, 2) if isinstance(v, float) else v)
            for k, v in analysis.values.items()
            if k in config.outputs
        },
        "triggers": {tag: names for tag, names in analysis.triggers.items() if names},
    }

    if analysis.warnings:
        result["warnings"] = analysis.warnings

    chips = _build_chips_summary(normalized)
    if chips:
        result["chips"] = chips

    related_news = _filter_news_for_ticker(all_news or [], normalized)
    if related_news:
        result["news"] = related_news

    return result


def get_latest_price(symbol: str) -> dict:
    quote = get_quote(symbol)
    return {
        "symbol": quote.symbol,
        "price": quote.price,
        "change": quote.change,
        "change_pct": quote.change_pct,
        "source": quote.source,
    }


def get_technical_data(symbol: str) -> dict:
    return build_stock_analysis(symbol)


def get_history_records(symbol: str, days: int = 100) -> list[dict]:
    df = get_history_dataframe(symbol, days=days)
    records: list[dict] = []
    for row in df.to_dict("records"):
        raw_date = row["date"]
        records.append(
            {
                "date": _format_date(raw_date),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]) if row["volume"] is not None else 0,
            }
        )
    return records


def get_history_dataframe(symbol: str, days: int = 120) -> pd.DataFrame:
    bars = get_bars(symbol, lookback_days=days)
    if not bars:
        raise ValueError(f"No bar data available for {normalize_symbol(symbol)}")

    rows = [
        {
            "date": bar.bar_time,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for bar in bars
    ]
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    if "volume" in df.columns:
        df["volume"] = df["volume"].fillna(0)
    return df


def get_market_news_raw(category: str = "tw_stock", limit: int = 10) -> list[dict]:
    categories = [category] if category != "all" else ["headlines", "tw_stock"]
    return _public_news_items(_fetch_news(categories=categories, limit=limit))


def save_briefing(data: dict, symbols: list[str] | None = None) -> None:
    MARKET_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H%M")
    normalized_symbols = [normalize_symbol(symbol) for symbol in symbols or []]

    if normalized_symbols:
        for symbol in normalized_symbols:
            ticker_id = strip_suffix(symbol)
            stock_data = next(
                (item for item in data.get("stocks", []) if strip_suffix(item.get("symbol", "")) == ticker_id),
                None,
            )
            if not stock_data:
                continue

            payload = {
                "date": data.get("date"),
                "session": data.get("session"),
                "market": data.get("market"),
                "stock": stock_data,
            }
            path = MARKET_SNAPSHOTS_DIR / f"{timestamp}-{ticker_id}.yaml"
            with open(path, "w", encoding="utf-8") as handle:
                yaml.dump(payload, handle, allow_unicode=True, default_flow_style=False, sort_keys=False)
    else:
        path = MARKET_SNAPSHOTS_DIR / f"{timestamp}.yaml"
        with open(path, "w", encoding="utf-8") as handle:
            yaml.dump(data, handle, allow_unicode=True, default_flow_style=False, sort_keys=False)

    _cleanup_market_snapshots()


def _build_chips_summary(symbol: str) -> dict | None:
    rows = get_chips(symbol, lookback_days=20)

    if not rows:
        return None

    latest = rows[-1]
    result: dict[str, object] = {"trade_date": latest.trade_date.isoformat()}

    for field in ("foreign_net", "trust_net", "dealer_net", "margin_balance"):
        value = getattr(latest, field)
        if value is not None:
            result[field] = value

    margin_trend = _margin_balance_trend(rows)
    if margin_trend:
        result["margin_balance_trend"] = margin_trend

    streak_fields = {
        "foreign_net": "foreign_investors",
        "trust_net": "investment_trust",
        "dealer_net": "dealer",
    }
    for field, label in streak_fields.items():
        streak = _build_net_streak(rows, field)
        if streak:
            result[label] = streak

    return result if len(result) > 1 else None


def _build_net_streak(rows: list, field: str) -> str | None:
    consecutive = 0
    direction: str | None = None

    for row in reversed(rows):
        value = getattr(row, field)
        if value is None or value == 0:
            break
        current = "BUY" if value > 0 else "SELL"
        if direction is None:
            direction = current
        if current != direction:
            break
        consecutive += 1

    if not direction or consecutive == 0:
        return None
    return f"NET_{direction}_{consecutive}_DAYS"


def _margin_balance_trend(rows: list) -> str | None:
    balances = [row.margin_balance for row in rows if row.margin_balance is not None]
    if len(balances) < 2:
        return None

    current = balances[-1]
    baseline = balances[-6] if len(balances) >= 6 else balances[0]
    if baseline <= 0:
        return None

    change_pct = (current - baseline) / baseline * 100
    if change_pct > 5:
        return "INCREASING"
    if change_pct < -5:
        return "DECREASING"
    return "STABLE"


def _get_index_data() -> dict:
    quote = get_quote("^TWII")

    return {
        "taiex": round(quote.price, 0) if quote.price is not None else None,
        "change_pct": round(quote.change_pct, 2) if quote.change_pct is not None else None,
    }


def _classify_index_trend() -> str:
    df = get_history_dataframe("^TWII", days=60)
    ma20 = ta.sma(df["close"], length=20)
    if ma20 is None or ma20.empty or pd.isna(ma20.iloc[-1]):
        return "UNKNOWN"
    return "ABOVE_MA20" if float(df["close"].iloc[-1]) > float(ma20.iloc[-1]) else "BELOW_MA20"


def _fetch_news(categories: list[str] | None = None, limit: int = 30) -> list[dict]:
    categories = categories or ["headlines", "tw_stock"]
    items: list[dict] = []

    with httpx.Client(timeout=10) as client:
        for category in categories:
            api_category = NEWS_CATEGORIES.get(category, category)
            url = CNYES_API.format(cat=api_category, limit=limit)
            try:
                response = client.get(url, headers=_HEADERS)
                response.raise_for_status()
            except Exception:
                continue
            items.extend(response.json().get("items", {}).get("data", []))

    return _parse_news_items(items)


def _parse_news_items(raw_items: list[dict]) -> list[dict]:
    seen_titles: set[str] = set()
    results: list[dict] = []
    for item in raw_items:
        title = item.get("title", "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)

        news_id = item.get("newsId", "")
        published_at = item.get("publishAt")
        stock_codes = [market.get("code", "") for market in item.get("market", []) if market.get("code")]
        results.append(
            {
                "title": title,
                "url": CNYES_URL_BASE.format(news_id=news_id) if news_id else "",
                "published": datetime.fromtimestamp(published_at).strftime("%Y-%m-%d %H:%M") if published_at else "",
                "symbols": stock_codes[:3],
                "_all_symbols": stock_codes,
            }
        )
    return results


def _filter_news_for_ticker(news: list[dict], symbol: str) -> list[dict]:
    ticker_id = strip_suffix(symbol)
    return [
        {"title": item["title"], "url": item["url"], "published": item["published"]}
        for item in news
        if ticker_id in item.get("_all_symbols", item.get("symbols", []))
    ]


def _public_news_items(news: list[dict]) -> list[dict]:
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "published": item.get("published", ""),
            "symbols": item.get("symbols", []),
        }
        for item in news
    ]


def _cleanup_market_snapshots(keep_days: int = MARKET_SNAPSHOTS_KEEP_DAYS) -> None:
    if not MARKET_SNAPSHOTS_DIR.exists():
        return

    cutoff = datetime.now() - timedelta(days=keep_days)
    for path in MARKET_SNAPSHOTS_DIR.glob("*.yaml"):
        try:
            date_part = "-".join(path.stem.split("-")[:4])
            file_dt = datetime.strptime(date_part, "%Y-%m-%d-%H%M")
        except (IndexError, ValueError):
            continue
        if file_dt < cutoff:
            path.unlink()


def _format_date(value: object) -> str:
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)

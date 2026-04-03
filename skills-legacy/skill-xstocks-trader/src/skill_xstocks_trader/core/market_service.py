"""
market_service.py — Market data and technical analysis for xStocks (Hyperliquid via CCXT).

Provides:
  - Live OHLCV data from Hyperliquid
  - SPY/QQQ macro regime detection
  - Per-symbol technical analysis integration
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import ccxt
import pandas as pd
import yaml

from skill_xstocks_trader.core.account_paths import (
    MARKET_SNAPSHOTS_DIR,
    PAIRS_FILE,
    TECHNICAL_CONFIG_FILE,
)
from skill_xstocks_trader.core.technical_engine import (
    build_technical_analysis,
    get_expression_definitions,
    get_indicator_definitions,
    load_analysis_config,
)

# ── Exchange singleton ───────────────────────────────────────────────────────

_exchange: ccxt.Exchange | None = None


def _get_exchange() -> ccxt.Exchange:
    global _exchange
    if _exchange is None:
        _exchange = ccxt.hyperliquid({"enableRateLimit": True})
        _exchange.load_markets()
    return _exchange


# ── Public API ───────────────────────────────────────────────────────────────


def build_market_report(symbols: list[str] | None = None) -> dict:
    """Build a full market report: regime overview + per-symbol analysis."""
    if not symbols:
        return build_overview()

    overview = build_overview()
    stocks: list[dict] = []
    for symbol in symbols:
        stocks.append(build_stock_analysis(symbol))

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "regime": overview["regime"],
        "stocks": stocks,
    }


def build_overview() -> dict:
    """SPY/QQQ macro regime snapshot."""
    regime = _compute_regime()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "market": "24/7 (Hyperliquid DEX)",
        "regime": regime,
    }


def build_stock_analysis(symbol: str) -> dict:
    """Full technical analysis for a single symbol."""
    config = load_analysis_config()
    quote = get_latest_price(symbol)
    df = get_history_dataframe(symbol, timeframe="1h", limit=200)
    analysis = build_technical_analysis(
        df,
        indicators=get_indicator_definitions(config),
        expressions=get_expression_definitions(config),
    )

    result: dict = {
        "symbol": symbol,
        "quote": quote,
        "metrics": {
            k: (round(v, 2) if isinstance(v, float) else v)
            for k, v in analysis.values.items()
            if k in config.outputs
        },
        "triggers": {tag: names for tag, names in analysis.triggers.items() if names},
    }

    if analysis.warnings:
        result["warnings"] = analysis.warnings

    return result


def get_latest_price(symbol: str) -> dict:
    """Fetch current ticker price from Hyperliquid."""
    exchange = _get_exchange()
    try:
        ticker = exchange.fetch_ticker(symbol)
        return {
            "symbol": symbol,
            "price": ticker.get("last"),
            "change_pct": ticker.get("percentage"),
            "high_24h": ticker.get("high"),
            "low_24h": ticker.get("low"),
            "volume_24h": ticker.get("baseVolume"),
        }
    except Exception as e:
        return {"symbol": symbol, "price": None, "error": str(e)}


def get_history_dataframe(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 200,
) -> pd.DataFrame:
    """Fetch OHLCV candles from Hyperliquid and return as a DataFrame."""
    exchange = _get_exchange()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

    if not ohlcv:
        raise ValueError(f"No OHLCV data available for {symbol}")

    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def get_regime_pairs() -> list[str]:
    """Read regime pairs from pairs.yaml config."""
    if not PAIRS_FILE.exists():
        return ["SPY/USDC"]
    with open(PAIRS_FILE, "r") as f:
        data = yaml.safe_load(f) or {}
    return [p["symbol"] for p in data.get("regime_pairs", [{"symbol": "SPY/USDC"}])]


def save_briefing(data: dict, symbols: list[str] | None = None) -> None:
    """Save market snapshot to disk."""
    MARKET_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H%M")

    path = MARKET_SNAPSHOTS_DIR / f"{timestamp}.yaml"
    with open(path, "w", encoding="utf-8") as handle:
        yaml.dump(data, handle, allow_unicode=True, default_flow_style=False, sort_keys=False)

    _cleanup_market_snapshots()


# ── Regime Detection ─────────────────────────────────────────────────────────


def _compute_regime() -> dict:
    """Compute macro regime based on SPY price vs 200-period SMA."""
    regime_symbols = get_regime_pairs()
    results: dict = {}

    for symbol in regime_symbols:
        try:
            df = get_history_dataframe(symbol, timeframe="1d", limit=250)
            if len(df) < 200:
                results[symbol] = {"status": "INSUFFICIENT_DATA"}
                continue

            close = float(df["close"].iloc[-1])
            sma_200 = float(df["close"].rolling(200).mean().iloc[-1])
            sma_50 = float(df["close"].rolling(50).mean().iloc[-1])
            distance_200_pct = ((close - sma_200) / sma_200) * 100

            if close > sma_200 and close > sma_50:
                label = "STRONG_BULL"
            elif close > sma_200 and close < sma_50:
                label = "BULL_PULLBACK"
            elif close < sma_200 and close > sma_50:
                label = "TRANSITION"
            else:
                label = "STRONG_BEAR"

            results[symbol] = {
                "close": round(close, 2),
                "sma_50": round(sma_50, 2),
                "sma_200": round(sma_200, 2),
                "distance_200_pct": round(distance_200_pct, 2),
                "label": label,
            }
        except Exception as e:
            results[symbol] = {"status": "ERROR", "error": str(e)}

    return results


# ── Helpers ──────────────────────────────────────────────────────────────────


def _cleanup_market_snapshots(keep_days: int = 7) -> None:
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

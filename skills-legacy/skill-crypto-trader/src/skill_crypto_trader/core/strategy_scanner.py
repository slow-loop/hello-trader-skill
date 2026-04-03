"""Scan strategies against local market data to find current candidates.

This is intentionally lightweight:
- Each strategy remains responsible for its own informative pairs and filters.
- The scanner only asks "is this strategy currently producing signals?"
- If a strategy exposes a ``regime_ok`` column, we use that as broader
  eligibility and keep entry signals as a separate metric.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd
from freqtrade.strategy import IStrategy

from skill_crypto_trader.core.freqtrade_config import load_base_config
from skill_crypto_trader.core.strategy_registry import load_registry
from skill_crypto_trader.journal.helpers import get_freqtrade_userdata, get_strategy_dir

DEFAULT_ALLOWED_STATUSES = {"candidate", "validated", "active", "deployed", "watch"}


def _timeframe_to_timedelta(timeframe: str) -> timedelta:
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def _default_exchange() -> str:
    try:
        return load_base_config().get("exchange", {}).get("name", "bybit")
    except FileNotFoundError:
        return "bybit"


class LocalDataProvider:
    """Minimal DataProvider stub for strategy informative pair loading."""

    def __init__(self, data_root: Path):
        self.data_root = data_root
        self._cache: dict[tuple[str, str], pd.DataFrame] = {}

    def get_pair_dataframe(self, pair: str, timeframe: str) -> pd.DataFrame:
        key = (pair, timeframe)
        if key in self._cache:
            return self._cache[key].copy()

        path = self.data_root / f"{pair.replace('/', '_')}-{timeframe}.feather"
        if not path.exists():
            raise FileNotFoundError(f"Missing market data: {path}")

        df = pd.read_feather(path)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], utc=True)
        self._cache[key] = df
        return df.copy()


def _load_strategy_module(strategy_path: Path) -> ModuleType:
    module_id = hashlib.md5(str(strategy_path).encode("utf-8")).hexdigest()[:10]
    module_name = f"_strategy_scan_{strategy_path.stem.lower()}_{module_id}"
    spec = importlib.util.spec_from_file_location(module_name, strategy_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load strategy module from {strategy_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _find_strategy_class(module: ModuleType) -> type[IStrategy]:
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue
        if issubclass(obj, IStrategy) and obj is not IStrategy:
            return obj
    raise ValueError(f"No IStrategy subclass found in {module.__file__}")


def _instantiate_strategy(strategy_path: Path) -> IStrategy:
    module = _load_strategy_module(strategy_path)
    strategy_cls = _find_strategy_class(module)
    return strategy_cls({})


def _coerce_signal_series(dataframe: pd.DataFrame, column: str) -> pd.Series:
    if column not in dataframe.columns:
        return pd.Series(False, index=dataframe.index)
    series = dataframe[column].fillna(0)
    return series.astype(float) > 0


def _coerce_bool_series(dataframe: pd.DataFrame, column: str) -> pd.Series:
    if column not in dataframe.columns:
        return pd.Series(False, index=dataframe.index)
    return dataframe[column].fillna(False).astype(bool)


def _evaluate_pair(
    strategy: IStrategy,
    pair: str,
    lookback_bars: int,
    *,
    data_provider: LocalDataProvider,
    now_utc: datetime,
) -> dict[str, Any]:
    timeframe = getattr(strategy, "timeframe", "1h")

    try:
        dataframe = data_provider.get_pair_dataframe(pair, timeframe)
    except FileNotFoundError as exc:
        return {
            "pair": pair,
            "eligible": False,
            "blocked_reason": "missing_data",
            "detail": str(exc),
        }

    if dataframe.empty:
        return {
            "pair": pair,
            "eligible": False,
            "blocked_reason": "empty_data",
        }

    last_candle_at = pd.Timestamp(dataframe["date"].iloc[-1]).to_pydatetime()
    timeframe_delta = _timeframe_to_timedelta(timeframe)
    staleness = now_utc - last_candle_at
    max_staleness = max(timeframe_delta * 3, timedelta(hours=48))
    is_stale = staleness > max_staleness
    if is_stale:
        return {
            "pair": pair,
            "eligible": False,
            "blocked_reason": "stale_data",
            "last_candle_at": last_candle_at.isoformat(),
            "staleness_hours": round(staleness.total_seconds() / 3600, 2),
        }

    metadata = {"pair": pair}
    analyzed = strategy.populate_indicators(dataframe.copy(), metadata)
    analyzed = strategy.populate_entry_trend(analyzed, metadata)

    recent = analyzed.tail(lookback_bars)
    signal_mask = _coerce_signal_series(analyzed, "enter_long")
    recent_signal_mask = signal_mask.tail(lookback_bars)
    regime_mask = _coerce_bool_series(analyzed, "regime_ok")
    recent_regime_mask = regime_mask.tail(lookback_bars)

    latest_signal_at = None
    if signal_mask.any():
        latest_signal_at = pd.Timestamp(analyzed.loc[signal_mask, "date"].iloc[-1]).isoformat()

    regime_pass_count = int(recent_regime_mask.sum()) if "regime_ok" in analyzed.columns else None
    recent_signal_count = int(recent_signal_mask.sum())
    last_bar_signal = bool(recent_signal_mask.iloc[-1]) if not recent.empty else False

    if regime_pass_count is not None:
        eligible = regime_pass_count > 0
        blocked_reason = "regime_blocked" if not eligible else None
    else:
        eligible = recent_signal_count > 0
        blocked_reason = "no_recent_signals" if not eligible else None

    return {
        "pair": pair,
        "eligible": eligible,
        "blocked_reason": blocked_reason,
        "last_bar_signal": last_bar_signal,
        "recent_signal_count": recent_signal_count,
        "regime_pass_count": regime_pass_count,
        "latest_signal_at": latest_signal_at,
        "last_candle_at": last_candle_at.isoformat(),
    }


def scan_strategy_entry(
    entry: dict[str, Any],
    *,
    lookback_bars: int = 96,
    strategy_dir: Path | None = None,
    data_root: Path | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    strategy_dir = strategy_dir or get_strategy_dir()
    exchange = data_root.parent.name if data_root is not None else _default_exchange()
    data_root = data_root or (get_freqtrade_userdata() / "data" / exchange)
    now_utc = now_utc or datetime.now(timezone.utc)

    strategy_file = entry.get("strategy_file") or f"{entry['name']}.py"
    strategy_path = strategy_dir / strategy_file
    if not strategy_path.exists():
        return {
            "name": entry["name"],
            "status": entry.get("status", ""),
            "timeframe": entry.get("timeframe", ""),
            "eligible": False,
            "blocked_reason": "missing_strategy_file",
            "strategy_file": strategy_file,
        }

    strategy = _instantiate_strategy(strategy_path)
    strategy.dp = LocalDataProvider(data_root)

    pairs = entry.get("pairs") or ["BTC/USDT"]
    pair_results = [
        _evaluate_pair(strategy, pair, lookback_bars, data_provider=strategy.dp, now_utc=now_utc)
        for pair in pairs
    ]

    eligible_pairs = [item for item in pair_results if item.get("eligible")]
    active_pairs = [item["pair"] for item in eligible_pairs if item.get("last_bar_signal")]
    latest_signal_at = None
    signal_timestamps = [
        item["latest_signal_at"] for item in pair_results if item.get("latest_signal_at")
    ]
    if signal_timestamps:
        latest_signal_at = max(signal_timestamps)

    total_recent_signals = sum(item.get("recent_signal_count", 0) for item in pair_results)
    score = (len(active_pairs) * 10_000) + (total_recent_signals * 100) + len(eligible_pairs)

    blocked_reasons: dict[str, int] = {}
    for item in pair_results:
        reason = item.get("blocked_reason")
        if reason:
            blocked_reasons[reason] = blocked_reasons.get(reason, 0) + 1

    return {
        "name": entry["name"],
        "status": entry.get("status", ""),
        "strategy_file": strategy_file,
        "timeframe": getattr(strategy, "timeframe", entry.get("timeframe", "")),
        "eligible": len(eligible_pairs) > 0,
        "eligible_pairs": len(eligible_pairs),
        "scanned_pairs": len(pair_results),
        "active_signal_pairs": active_pairs,
        "total_recent_signals": total_recent_signals,
        "latest_signal_at": latest_signal_at,
        "score": score,
        "blocked_reasons": blocked_reasons,
        "pair_summaries": pair_results,
    }


def scan_registry_candidates(
    *,
    lookback_bars: int = 96,
    limit: int = 10,
    statuses: set[str] | None = None,
    registry_entries: list[dict[str, Any]] | None = None,
    strategy_dir: Path | None = None,
    data_root: Path | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    registry_entries = registry_entries or load_registry()
    statuses = statuses or DEFAULT_ALLOWED_STATUSES
    now_utc = now_utc or datetime.now(timezone.utc)
    exchange = data_root.parent.name if data_root is not None else _default_exchange()
    data_root = data_root or (get_freqtrade_userdata() / "data" / exchange)

    scanned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for entry in registry_entries:
        status = entry.get("status", "")
        if status and status not in statuses:
            skipped.append({"name": entry["name"], "status": status, "reason": "status_filtered"})
            continue
        scanned.append(
            scan_strategy_entry(
                entry,
                lookback_bars=lookback_bars,
                strategy_dir=strategy_dir,
                data_root=data_root,
                now_utc=now_utc,
            )
        )

    scanned.sort(
        key=lambda item: (
            item.get("eligible", False),
            len(item.get("active_signal_pairs", [])),
            item.get("total_recent_signals", 0),
            item.get("eligible_pairs", 0),
            item.get("latest_signal_at") or "",
        ),
        reverse=True,
    )

    candidates = [item for item in scanned if item.get("eligible")][:limit]
    blocked = [item for item in scanned if not item.get("eligible")]

    return {
        "scanned_at": now_utc.isoformat(),
        "exchange": exchange,
        "lookback_bars": lookback_bars,
        "candidate_count": len(candidates),
        "blocked_count": len(blocked),
        "candidates": candidates,
        "blocked": blocked,
        "skipped": skipped,
    }

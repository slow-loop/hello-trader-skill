"""Local workspace files for tw-trader.

Handles journal / lessons / brief YAML I/O plus the watchlist
path. Watchlist content lives in market_core.watchlist; this module
only owns the path helpers and the non-market tw-trader artifacts.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from market_core import (
    AnalysisSettings,
    EvaluatedWatchlistConfig,
    MarketConfig,
    MarketRuntimeConfig,
    WatchlistConfig,
    WatchlistItem,
    get_market_profile,
)
from market_core.watchlist import (
    delete_watchlist_item as _delete_watchlist_item,
    evaluate_watchlist,
    load_watchlist as _load_watchlist,
    save_watchlist as _save_watchlist,
    upsert_watchlist_item as _upsert_watchlist_item,
)

from tw_trader.events import append_event

SKILL_ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_SUBDIR = "data/account"


class JournalEntry(BaseModel):
    at: str = ""
    type: str = "note"
    actions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class JournalDocument(BaseModel):
    date: str
    entries: list[JournalEntry] = Field(default_factory=list)


def workspace_root() -> Path:
    env = os.getenv("TW_TRADER_ROOT")
    return Path(env).expanduser() if env else SKILL_ROOT


def account_dir() -> Path:
    return workspace_root() / ACCOUNT_SUBDIR


def watchlist_path() -> Path:
    return account_dir() / "watchlist.yaml"


def journals_dir() -> Path:
    return account_dir() / "journals"


def journal_path(date_str: str) -> Path:
    return journals_dir() / f"{date_str}.yaml"


def lessons_path() -> Path:
    return account_dir() / "lessons.md"


def briefs_dir() -> Path:
    return account_dir() / "briefs"


def brief_template_path() -> Path:
    return briefs_dir() / "template" / "brief.template.yaml"


# --- Watchlist (delegates to market_core.watchlist) -----------------


def load_watchlist() -> WatchlistConfig:
    return _load_watchlist(watchlist_path())


def save_watchlist(watchlist: WatchlistConfig) -> None:
    _save_watchlist(watchlist_path(), watchlist)


def upsert_watchlist_item(item: WatchlistItem) -> WatchlistConfig:
    return _upsert_watchlist_item(watchlist_path(), item)


def delete_watchlist_item(symbol: str) -> WatchlistConfig:
    return _delete_watchlist_item(watchlist_path(), symbol)


def _load_analysis_settings() -> AnalysisSettings:
    path = workspace_root() / "data/config/technical_config.yaml"
    if not path.exists():
        return AnalysisSettings()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"technical config must be a mapping: {path}")
    return AnalysisSettings.model_validate(raw)


def _market_config() -> MarketRuntimeConfig:
    path = workspace_root() / "data/config/workspace.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    market = (raw or {}).get("market") or {}
    return MarketRuntimeConfig(
        market=MarketConfig(
            profile=market.get("profile", "tw_equity"),
            benchmark_symbol=market.get("benchmark_symbol"),
        ),
        analysis=_load_analysis_settings(),
    )


def load_evaluated_watchlist() -> EvaluatedWatchlistConfig:
    watchlist = load_watchlist()
    config = _market_config()
    profile = get_market_profile(config.market.profile)
    return evaluate_watchlist(watchlist, config, profile)


# --- Journal -------------------------------------------------------


def load_journal(date_str: str) -> JournalDocument:
    path = journal_path(date_str)
    if not path.exists():
        return JournalDocument(date=date_str)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise ValueError(f"journal must be a list: {path}")
    entries = [JournalEntry.model_validate(item) for item in raw]
    return JournalDocument(date=date_str, entries=entries)


def append_journal_entry(date_str: str, entry: JournalEntry) -> JournalDocument:
    document = load_journal(date_str)
    normalized = entry.model_copy()
    if not normalized.at:
        normalized.at = datetime.now().strftime("%H:%M")
    document.entries.append(normalized)
    payload = [item.model_dump(mode="json", exclude_none=True) for item in document.entries]
    _write_yaml_atomic(journal_path(date_str), payload)
    append_event(
        "journal.add",
        {"date": date_str, "entry": normalized.model_dump(mode="json", exclude_none=True)},
    )
    return document


def list_journals(limit: int = 5) -> list[dict]:
    directory = journals_dir()
    if not directory.exists():
        return []
    summaries: list[dict] = []
    for path in sorted(directory.glob("*.yaml"), reverse=True)[:limit]:
        document = load_journal(path.stem)
        summaries.append({"date": path.stem, "entry_count": len(document.entries)})
    return summaries


# --- Lessons -------------------------------------------------------


def load_lessons() -> str:
    path = lessons_path()
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def save_lessons(content: str) -> None:
    _write_text_atomic(lessons_path(), content)


# --- Briefs --------------------------------------------------------


def init_brief(now: datetime | None = None) -> Path:
    ts = now or datetime.now()
    filename = ts.strftime("%Y-%m-%d-%H%M") + ".yaml"
    path = briefs_dir() / filename
    template_file = brief_template_path()
    if template_file.exists():
        content = template_file.read_text(encoding="utf-8")
        content = content.replace('"YYYY-MM-DD"', f'"{ts.strftime("%Y-%m-%d")}"')
    else:
        content = yaml.safe_dump(
            {"date": ts.strftime("%Y-%m-%d"), "status": "draft"},
            allow_unicode=True,
            sort_keys=False,
        )
    _write_text_atomic(path, content)
    append_event("brief.init", {"path": str(path.relative_to(workspace_root()))})
    return path


def commit_brief(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"brief must be a yaml mapping: {path}")
    if "date" not in raw:
        raise ValueError(f"brief missing required field 'date': {path}")
    append_event(
        "brief.commit",
        {"path": str(path.relative_to(workspace_root())), "date": raw.get("date")},
    )
    return raw


def latest_brief_draft() -> Path | None:
    directory = briefs_dir()
    if not directory.exists():
        return None
    candidates = [p for p in directory.glob("*.yaml") if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_brief(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"brief must be a yaml mapping: {path}")
    return raw


# --- Atomic write helpers -----------------------------------------


def _write_yaml_atomic(path: Path, data: object) -> None:
    serialized = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    _write_text_atomic(path, serialized)


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        Path(tmp_name).replace(path)
    finally:
        tmp_path = Path(tmp_name)
        if tmp_path.exists():
            tmp_path.unlink()

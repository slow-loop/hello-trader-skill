"""Local workspace files for tw-trader.

Handles journal / lessons YAML I/O plus the watchlist path. Watchlist
content lives in market_core.watchlist; this module only owns the path
helpers and the non-market tw-trader artifacts. Briefs are plain
markdown under data/account/research/ (no dedicated helpers).
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

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
PROJECT_ROOT = Path(__file__).resolve().parents[4]
ACCOUNT_SUBDIR = "data/account"


class JournalEntry(BaseModel):
    at: str = ""
    type: str = "note"
    round: int = 1
    actions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class JournalDocument(BaseModel):
    date: str
    entries: list[JournalEntry] = Field(default_factory=list)


def workspace_root() -> Path:
    """Skill root — holds static config under config/."""
    env = os.getenv("TW_TRADER_ROOT")
    return Path(env).expanduser() if env else SKILL_ROOT


def data_root() -> Path:
    """Runtime data root — holds account/, posts/ etc. Defaults to repo root."""
    env = os.getenv("TW_TRADER_DATA_ROOT")
    return Path(env).expanduser() if env else PROJECT_ROOT


def account_dir() -> Path:
    return data_root() / ACCOUNT_SUBDIR


def watchlist_path() -> Path:
    return account_dir() / "watchlist.yaml"


def journals_dir() -> Path:
    return account_dir() / "journals"


def journal_path(date_str: str) -> Path:
    return journals_dir() / f"{date_str}.yaml"


def lessons_path() -> Path:
    return account_dir() / "lessons.md"


def screener_dir() -> Path:
    return account_dir() / "screener"


def screener_snapshot_path(date_str: str, suffix: str | None = None) -> Path:
    name = f"{date_str}-{suffix}.json" if suffix else f"{date_str}.json"
    return screener_dir() / name


# --- Watchlist (delegates to market_core.watchlist) -----------------


def load_watchlist() -> WatchlistConfig:
    return _load_watchlist(watchlist_path())


def save_watchlist(watchlist: WatchlistConfig) -> None:
    _save_watchlist(watchlist_path(), watchlist)


def upsert_watchlist_item(item: WatchlistItem) -> WatchlistConfig:
    result = _upsert_watchlist_item(watchlist_path(), item)
    append_event(
        "watchlist.update",
        {"symbol": item.symbol, "item": item.model_dump(mode="json", exclude_none=True)},
    )
    return result


def sync_watchlist_with_positions(held_symbols: set[str]) -> list[dict]:
    """Reconcile watchlist status with current positions.

    held_symbols: set of symbols currently held (any format, .TW suffix tolerated).
    Returns list of {symbol, from, to} for each status change.
    """
    held_norm = {s.removesuffix(".TW") for s in held_symbols}
    watchlist = load_watchlist()
    changes: list[dict] = []
    for item in watchlist.items:
        sym_norm = item.symbol.removesuffix(".TW")
        if sym_norm in held_norm and item.status != "hold":
            changes.append({"symbol": item.symbol, "from": item.status, "to": "hold"})
            item.status = "hold"
        elif sym_norm not in held_norm and item.status == "hold":
            changes.append({"symbol": item.symbol, "from": "hold", "to": "watch"})
            item.status = "watch"
    if changes:
        save_watchlist(watchlist)
        for change in changes:
            append_event("watchlist.status_sync", change)
    return changes


def delete_watchlist_item(symbol: str) -> WatchlistConfig:
    result = _delete_watchlist_item(watchlist_path(), symbol)
    append_event("watchlist.delete", {"symbol": symbol})
    return result


def _load_analysis_settings() -> AnalysisSettings:
    path = workspace_root() / "config/technical_config.yaml"
    if not path.exists():
        return AnalysisSettings()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"technical config must be a mapping: {path}")
    return AnalysisSettings.model_validate(raw)


def _market_config() -> MarketRuntimeConfig:
    path = workspace_root() / "config/workspace.yaml"
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
    append_event("lessons.set", {"length": len(content)})


# --- Research docs ------------------------------------------------


def research_dir() -> Path:
    return account_dir() / "research"


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
_FILENAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})-tw-(.+)$")
_BRIEF_HHMM_RE = re.compile(r"brief-(\d{2})(\d{2})$")


def add_doc(path: Path) -> dict:
    """Stamp created_at frontmatter + emit doc.add event.

    Brief files without HHMM suffix are renamed to
    ``{date}-tw-brief-{HHMM}.md`` using the system clock. created_at is
    idempotent: if already present in frontmatter it is preserved.
    """
    abs_path = Path(path).resolve()
    if not abs_path.exists():
        raise FileNotFoundError(abs_path)

    research = research_dir().resolve()
    if research not in abs_path.parents:
        raise ValueError(f"doc must live under {research}: {abs_path}")

    now = datetime.now().astimezone()
    name = abs_path.stem
    m = _FILENAME_RE.match(name)
    if not m:
        raise ValueError(f"filename must match YYYY-MM-DD-tw-<rest>.md: {name}")
    date_str, rest = m.group(1), m.group(2)

    if rest.startswith("brief"):
        kind = "brief"
        if not _BRIEF_HHMM_RE.match(rest):
            hhmm = now.strftime("%H%M")
            new_path = abs_path.with_name(f"{date_str}-tw-brief-{hhmm}.md")
            if new_path.exists():
                raise FileExistsError(new_path)
            abs_path.rename(new_path)
            abs_path = new_path
    else:
        kind = "symbol"

    raw = abs_path.read_text(encoding="utf-8")
    fm_match = _FRONTMATTER_RE.match(raw)
    created_at = now.isoformat(timespec="seconds")

    if fm_match:
        fm = yaml.safe_load(fm_match.group(1)) or {}
        if not isinstance(fm, dict):
            raise ValueError(f"frontmatter must be a mapping: {abs_path}")
        if "created_at" in fm:
            created_at = str(fm["created_at"])
        else:
            fm["created_at"] = created_at
            new_fm = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).rstrip()
            raw = f"---\n{new_fm}\n---\n" + raw[fm_match.end():]
            _write_text_atomic(abs_path, raw)
    else:
        new_fm = yaml.safe_dump(
            {"created_at": created_at}, allow_unicode=True, sort_keys=False
        ).rstrip()
        raw = f"---\n{new_fm}\n---\n\n" + raw
        _write_text_atomic(abs_path, raw)

    rel_path = str(abs_path.relative_to(data_root()))
    payload = {
        "path": rel_path,
        "kind": kind,
        "date": date_str,
        "created_at": created_at,
    }
    append_event("doc.add", payload)
    return payload


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

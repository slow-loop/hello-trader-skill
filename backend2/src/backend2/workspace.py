from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import tempfile

import yaml

from backend2.models import (
    JournalDocument,
    JournalEntry,
    JournalSummary,
    LessonsDocument,
    NewsConfig,
    WatchlistConfig,
    WatchlistItem,
    WorkspaceConfig,
    WorkspaceRuntimeConfig,
)
from market_core.technical import AnalysisConfig, ExpressionSpec, IndicatorSpec

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE_ROOT = "../skills/tw-trader"


def load_runtime_config() -> WorkspaceRuntimeConfig:
    root = _resolve_workspace_root(os.getenv("BACKEND2_WORKSPACE_ROOT", DEFAULT_WORKSPACE_ROOT))
    config_path = root / "data/config/workspace.yaml"
    raw_data = _load_yaml_mapping(config_path)

    workspace_raw = dict(raw_data.get("workspace") or {})
    workspace_raw["root_dir"] = str(root)
    raw_data["workspace"] = WorkspaceConfig.model_validate(workspace_raw).model_dump(mode="python")

    config = WorkspaceRuntimeConfig.model_validate(raw_data)
    if config.agent.prompt_file:
        config.agent.prompt_file = str(_workspace_file(root, config.agent.prompt_file))
    return config


def workspace_root(config: WorkspaceRuntimeConfig) -> Path | None:
    root = config.workspace.root_dir.strip()
    if not root:
        return None
    return Path(root)


def has_workspace(config: WorkspaceRuntimeConfig) -> bool:
    root = workspace_root(config)
    return root is not None and root.exists()


def load_analysis_config(config: WorkspaceRuntimeConfig) -> AnalysisConfig | None:
    root = workspace_root(config)
    if root is None:
        return None
    path = _workspace_file(root, config.workspace.technical_config)
    if path is None or not path.exists():
        return None

    raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw_data, dict):
        raise ValueError(f"technical config must be a mapping: {path}")

    indicators = [
        IndicatorSpec(
            name=str(item["name"]),
            ta_fn=str(item["ta_fn"]),
            params=dict(item.get("params") or {}),
        )
        for item in raw_data.get("indicators") or []
    ]
    expressions = [
        ExpressionSpec(
            name=str(item["name"]),
            expr=str(item["expr"]),
            tags=[str(tag) for tag in item.get("tags") or []],
        )
        for item in raw_data.get("expressions") or []
    ]
    outputs = [str(value) for value in raw_data.get("outputs") or []]
    return AnalysisConfig(indicators=indicators, expressions=expressions, outputs=outputs)


def load_news_config(config: WorkspaceRuntimeConfig) -> NewsConfig | None:
    root = workspace_root(config)
    if root is None:
        return None
    path = _workspace_file(root, config.workspace.news_config)
    if path is None or not path.exists():
        return None

    raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw_data, dict):
        raise ValueError(f"news config must be a mapping: {path}")
    return NewsConfig.model_validate(raw_data)


def load_watchlist(config: WorkspaceRuntimeConfig) -> WatchlistConfig:
    path = watchlist_path(config)
    if path is None:
        return config.watchlist
    if not path.exists():
        return WatchlistConfig()

    raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if isinstance(raw_data, dict):
        items = raw_data.get("items") or []
    elif isinstance(raw_data, list):
        items = raw_data
    else:
        raise ValueError(f"watchlist must be a list or mapping: {path}")

    return WatchlistConfig(items=[WatchlistItem.model_validate(item) for item in items])


def save_watchlist(config: WorkspaceRuntimeConfig, watchlist: WatchlistConfig) -> WatchlistConfig:
    path = _require_watchlist_path(config)
    payload = [item.model_dump(mode="json", exclude_none=True) for item in watchlist.items]
    _write_yaml_atomic(path, payload)
    return watchlist


def upsert_watchlist_item(config: WorkspaceRuntimeConfig, item: WatchlistItem) -> WatchlistConfig:
    current = load_watchlist(config)
    normalized_symbol = item.symbol.upper()
    replaced = False
    items: list[WatchlistItem] = []
    for existing in current.items:
        if existing.symbol.upper() == normalized_symbol:
            items.append(item)
            replaced = True
        else:
            items.append(existing)
    if not replaced:
        items.append(item)
    return save_watchlist(config, WatchlistConfig(items=items))


def list_journals(config: WorkspaceRuntimeConfig, limit: int = 5) -> list[JournalSummary]:
    directory = journals_dir(config)
    if directory is None or not directory.exists():
        return []

    summaries: list[JournalSummary] = []
    for path in sorted(directory.glob("*.yaml"), reverse=True)[:limit]:
        document = load_journal(config, path.stem)
        summaries.append(JournalSummary(date=path.stem, entry_count=len(document.entries)))
    return summaries


def load_journal(config: WorkspaceRuntimeConfig, date_str: str) -> JournalDocument:
    path = journal_path(config, date_str)
    if path is None or not path.exists():
        return JournalDocument(date=date_str)

    raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw_data, list):
        raise ValueError(f"journal must be a list: {path}")
    entries = [JournalEntry.model_validate(item) for item in raw_data]
    return JournalDocument(date=date_str, entries=entries)


def append_journal_entry(config: WorkspaceRuntimeConfig, date_str: str, entry: JournalEntry) -> JournalDocument:
    path = _require_journal_path(config, date_str)
    document = load_journal(config, date_str)
    normalized_entry = entry.model_copy()
    if not normalized_entry.at:
        normalized_entry.at = datetime.now().strftime("%H:%M")
    document.entries.append(normalized_entry)
    payload = [item.model_dump(mode="json", exclude_none=True) for item in document.entries]
    _write_yaml_atomic(path, payload)
    return document


def load_lessons(config: WorkspaceRuntimeConfig) -> LessonsDocument:
    path = lessons_path(config)
    if path is None or not path.exists():
        return LessonsDocument()
    return LessonsDocument(content=path.read_text(encoding="utf-8"))


def save_lessons(config: WorkspaceRuntimeConfig, lessons: LessonsDocument) -> LessonsDocument:
    path = _require_lessons_path(config)
    _write_text_atomic(path, lessons.content)
    return lessons


def watchlist_path(config: WorkspaceRuntimeConfig) -> Path | None:
    account_dir = account_dir_path(config)
    if account_dir is None:
        return None
    return account_dir / "watchlist.yaml"


def journals_dir(config: WorkspaceRuntimeConfig) -> Path | None:
    account_dir = account_dir_path(config)
    if account_dir is None:
        return None
    return account_dir / "journals"


def journal_path(config: WorkspaceRuntimeConfig, date_str: str) -> Path | None:
    directory = journals_dir(config)
    if directory is None:
        return None
    return directory / f"{date_str}.yaml"


def lessons_path(config: WorkspaceRuntimeConfig) -> Path | None:
    account_dir = account_dir_path(config)
    if account_dir is None:
        return None
    return account_dir / "lessons.md"


def account_dir_path(config: WorkspaceRuntimeConfig) -> Path | None:
    root = workspace_root(config)
    if root is None:
        return None

    account_dir = Path(config.workspace.account_dir)
    if account_dir.is_absolute():
        return account_dir
    return root / account_dir


def _workspace_file(root: Path, path_str: str) -> Path | None:
    if not path_str.strip():
        return None
    path = Path(path_str)
    if path.is_absolute():
        return path
    return root / path


def _require_watchlist_path(config: WorkspaceRuntimeConfig) -> Path:
    path = watchlist_path(config)
    if path is None:
        raise ValueError(f"workspace '{config.id}' has no local watchlist configured")
    return path


def _require_journal_path(config: WorkspaceRuntimeConfig, date_str: str) -> Path:
    path = journal_path(config, date_str)
    if path is None:
        raise ValueError(f"workspace '{config.id}' has no local journals configured")
    return path


def _require_lessons_path(config: WorkspaceRuntimeConfig) -> Path:
    path = lessons_path(config)
    if path is None:
        raise ValueError(f"workspace '{config.id}' has no local lessons configured")
    return path


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


def _resolve_workspace_root(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    if not path.exists():
        raise ValueError(f"workspace config file not found: {path}")

    raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw_data, dict):
        raise ValueError(f"workspace config must be a mapping: {path}")
    return dict(raw_data)

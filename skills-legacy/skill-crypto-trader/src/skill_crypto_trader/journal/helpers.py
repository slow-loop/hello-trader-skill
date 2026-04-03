"""Path utilities for journals, lessons, and data files."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

APP_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = APP_ROOT / "data"

AgentName = Literal["lab", "pm", "trader"]


def get_data_dir() -> Path:
    return DATA_DIR


def get_journal_dir(agent: AgentName) -> Path:
    d = DATA_DIR / "account" / "journals" / agent
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_journal_path(agent: AgentName) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    return get_journal_dir(agent) / f"{ts}.md"


def get_recent_journals(agent: AgentName, count: int = 3) -> list[Path]:
    d = get_journal_dir(agent)
    files = sorted(d.glob("*.md"), reverse=True)
    return files[:count]


def get_lessons_path(agent: AgentName) -> Path:
    return DATA_DIR / "account" / f"lessons_{agent}.md"


def get_registry_path() -> Path:
    return DATA_DIR / "strategies" / "registry.yaml"


def get_risk_rules_path() -> Path:
    return DATA_DIR / "config" / "risk_rules.yaml"


def get_state_dir() -> Path:
    d = DATA_DIR / "account" / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_regime_path() -> Path:
    return get_state_dir() / "market_regime.yaml"


def get_active_config_path() -> Path:
    return get_state_dir() / "active_config.yaml"


def get_freqtrade_userdata() -> Path:
    return APP_ROOT / "freqtrade_userdata"


def get_strategy_dir() -> Path:
    return get_freqtrade_userdata() / "strategies"

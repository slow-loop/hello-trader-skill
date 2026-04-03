from __future__ import annotations

from pathlib import Path

from skill_tw_trader import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data"
ACCOUNT_DIR = DATA_DIR / "account"

STATE_DIR = ACCOUNT_DIR / "state"
LEDGER_FILE = STATE_DIR / "ledger.json"
EQUITY_FILE = STATE_DIR / "equity.json"

MARKET_SNAPSHOTS_DIR = ACCOUNT_DIR / "market_snapshots"
JOURNALS_DIR = ACCOUNT_DIR / "journals"
JOURNAL_TEMPLATES_DIR = JOURNALS_DIR / "template"
RESEARCH_DIR = ACCOUNT_DIR / "research"
RESEARCH_TEMPLATES_DIR = RESEARCH_DIR / "template"

WATCHLIST_FILE = ACCOUNT_DIR / "watchlist.yaml"
WATCHLIST_TEMPLATE_FILE = ACCOUNT_DIR / "watchlist.example.yaml"
LESSONS_FILE = ACCOUNT_DIR / "lessons.md"


def journal_path(date_str: str) -> Path:
    return JOURNALS_DIR / f"{date_str}.yaml"


def ensure_account_dirs() -> None:
    for path in (
        STATE_DIR,
        MARKET_SNAPSHOTS_DIR,
        JOURNALS_DIR,
        JOURNAL_TEMPLATES_DIR,
        RESEARCH_DIR,
        RESEARCH_TEMPLATES_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# ── Account State ────────────────────────────────────────────────────────────
ACCOUNT_DIR = PROJECT_ROOT / "data" / "account"
STATE_DIR = ACCOUNT_DIR / "state"
LEDGER_FILE = STATE_DIR / "ledger.json"
EQUITY_FILE = STATE_DIR / "equity.json"
JOURNALS_DIR = ACCOUNT_DIR / "journals"
WATCHLIST_FILE = ACCOUNT_DIR / "watchlist.yaml"
LESSONS_FILE = ACCOUNT_DIR / "lessons.md"
MARKET_SNAPSHOTS_DIR = ACCOUNT_DIR / "market_snapshots"

# ── Config ───────────────────────────────────────────────────────────────────
CONFIG_DIR = PROJECT_ROOT / "data" / "config"
TECHNICAL_CONFIG_FILE = CONFIG_DIR / "technical_config.yaml"
PAIRS_FILE = CONFIG_DIR / "pairs.yaml"


def ensure_account_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    JOURNALS_DIR.mkdir(parents=True, exist_ok=True)
    MARKET_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

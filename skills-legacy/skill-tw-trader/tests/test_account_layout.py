from __future__ import annotations

import json
from unittest.mock import patch

from skill_tw_trader.core import trading_engine


def test_initialize_ledger_resets_equity_file_in_account_state(tmp_path):
    ledger_path = tmp_path / "accounts" / "state" / "ledger.json"
    equity_path = tmp_path / "accounts" / "state" / "equity.json"

    with (
        patch.object(trading_engine, "LEDGER_FILE", ledger_path),
        patch.object(trading_engine, "EQUITY_FILE", equity_path),
        patch.object(trading_engine, "ensure_account_dirs", return_value=None),
    ):
        trading_engine._save_equity_curve([{"date": "2026-03-01", "account_value": 12345}])

        result = trading_engine.initialize_ledger(initial_cash=500_000, force=True)

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    equity = json.loads(equity_path.read_text(encoding="utf-8"))

    assert "ledger.json" in result
    assert "equity.json" in result
    assert ledger["cash"] == 500_000.0
    assert equity == []

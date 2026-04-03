from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

import sys

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from skill_poly_trader.cli import main


class CliTests(unittest.TestCase):
    def test_status_command_prints_json(self):
        status = {"cash": 10000, "open_positions": [], "history_count": 0}
        with patch("skill_poly_trader.cli.build_status", return_value=status):
            with patch("sys.stdout.write") as mock_write:
                code = main(["status"])

        self.assertEqual(code, 0)
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn('"cash": 10000', written)

    def test_run_command_uses_cycle(self):
        report = {"scanned": 12, "qualified": 1, "selected_trade": {"action": "BUY_YES"}}
        with patch("skill_poly_trader.cli.run_cycle", return_value=report) as mock_run:
            with patch("sys.stdout.write") as mock_write:
                code = main(["run", "--limit", "12", "--candidates", "6", "--paper-size", "25"])

        self.assertEqual(code, 0)
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn('"qualified": 1', written)
        mock_run.assert_called_once_with(limit=12, candidate_count=6, paper_size=25.0, dry_run=False)

    def test_scan_command_uses_scan_report(self):
        report = {"scanned": 2, "event_count": 1, "events": [{"slug": "test-event", "markets": [{"slug": "test-market"}]}], "snapshots": [{"slug": "test-market"}]}
        with patch("skill_poly_trader.cli.build_scan_report", return_value=report) as mock_scan:
            with patch("sys.stdout.write") as mock_write:
                code = main(["scan", "--limit", "8", "--candidates", "3"])

        self.assertEqual(code, 0)
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn('"scanned": 2', written)
        mock_scan.assert_called_once_with(limit=8, candidate_count=3)

    def test_record_command_exits_cleanly_on_runtime_error(self):
        with patch("skill_poly_trader.cli.record_agent_decision", side_effect=RuntimeError("duplicate position")):
            with patch("sys.stderr.write") as mock_write:
                with self.assertRaises(SystemExit) as exc:
                    main(["record", "--slug", "test-market", "--model-yes", "0.42"])

        self.assertEqual(exc.exception.code, 1)
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("duplicate position", written)

    def test_close_command_exits_cleanly_on_runtime_error(self):
        with patch("skill_poly_trader.cli.close_position", side_effect=RuntimeError("position not found")):
            with patch("sys.stderr.write") as mock_write:
                with self.assertRaises(SystemExit) as exc:
                    main(["close", "--slug", "test-market", "--outcome", "YES"])

        self.assertEqual(exc.exception.code, 1)
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("position not found", written)
    def test_init_command_calls_initialize_ledger(self):
        with patch("skill_poly_trader.cli.initialize_ledger", return_value="Initialized") as mock_init:
            code = main(["init", "--cash", "5000", "--force"])
        self.assertEqual(code, 0)
        mock_init.assert_called_once_with(initial_cash=5000.0, force=True)

    def test_equity_command_calls_snapshot_equity(self):
        with patch("skill_poly_trader.cli.snapshot_equity", return_value={"equity": 10000}) as mock_equity:
            with patch("sys.stdout.write") as mock_write:
                code = main(["equity"])
        self.assertEqual(code, 0)
        mock_equity.assert_called_once()
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn('"equity": 10000', written)

    def test_record_command_calls_record_agent_decision(self):
        report = {"selected_trade": {"action": "BUY_YES"}}
        with patch("skill_poly_trader.cli.record_agent_decision", return_value=report) as mock_record:
            with patch("sys.stdout.write") as mock_write:
                code = main(["record", "--slug", "test", "--model-yes", "0.5", "--paper-size", "50", "--reason", "my-reason"])
        self.assertEqual(code, 0)
        mock_record.assert_called_once_with(
            slug="test", model_yes=0.5, paper_size=50.0, reason="my-reason", dry_run=False
        )
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn('"BUY_YES"', written)

    def test_close_command_calls_close_position(self):
        report = {"action": "CLOSE", "pnl": 10}
        with patch("skill_poly_trader.cli.close_position", return_value=report) as mock_close:
            with patch("sys.stdout.write") as mock_write:
                code = main(["close", "--slug", "test", "--outcome", "SELL"])
        self.assertEqual(code, 0)
        mock_close.assert_called_once_with(slug="test", outcome="SELL")
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn('"pnl": 10', written)

from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

import sys

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from skill_poly_trader_v2.cli import main


class CliV2Tests(unittest.TestCase):
    def test_markets_command_prints_yaml(self):
        report = {
            "profile": "all",
            "limit": 80,
            "count": 1,
            "markets": [{"question": "Will test happen?", "slug": "test-market", "description": "Long detail"}],
        }
        with patch("skill_poly_trader_v2.cli.build_markets_report", return_value=report):
            with patch("sys.stdout.write") as mock_write:
                code = main(["markets", "--limit", "5"])

        self.assertEqual(code, 0)
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("count: 1", written)
        self.assertIn("slug: test-market", written)
        self.assertNotIn("Long detail", written)

    def test_markets_command_passes_profile(self):
        report = {"profile": "geo", "limit": 5, "count": 1, "markets": [{"slug": "iran-ceasefire"}]}
        with patch("skill_poly_trader_v2.cli.build_markets_report", return_value=report) as mock_markets:
            with patch("sys.stdout.write"):
                code = main(["markets", "--limit", "5", "--profile", "geo"])

        self.assertEqual(code, 0)
        mock_markets.assert_called_once_with(limit=5, profile_name="geo")

    def test_markets_command_uses_profile_default_limit(self):
        report = {"profile": "all", "limit": 80, "count": 1, "markets": [{"slug": "test-market"}]}
        with patch("skill_poly_trader_v2.cli.build_markets_report", return_value=report) as mock_markets:
            with patch("sys.stdout.write"):
                code = main(["markets"])

        self.assertEqual(code, 0)
        mock_markets.assert_called_once_with(limit=None, profile_name="all")

    def test_markets_command_verbose_keeps_full_market_payload(self):
        report = {
            "profile": "all",
            "limit": 80,
            "count": 1,
            "markets": [{"question": "Will test happen?", "slug": "test-market", "description": "Long detail"}],
        }
        with patch("skill_poly_trader_v2.cli.build_markets_report", return_value=report):
            with patch("sys.stdout.write") as mock_write:
                code = main(["markets", "--limit", "5", "--verbose"])

        self.assertEqual(code, 0)
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("Long detail", written)

    def test_market_command_prints_yaml(self):
        report = {
            "question": "Will test happen?",
            "slug": "test-market",
            "outcomes": ["Yes", "No"],
            "outcomeIndexMap": {"0": "Yes", "1": "No"},
        }
        with patch("skill_poly_trader_v2.cli.build_market_report", return_value=report):
            with patch("sys.stdout.write") as mock_write:
                code = main(["market", "--slug", "test-market"])

        self.assertEqual(code, 0)
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("question: Will test happen?", written)
        self.assertIn('- "Yes"', written)
        self.assertIn('  0: "Yes"', written)

    def test_status_command_prints_yaml(self):
        status = {"cash": 10000, "open_positions": [], "history_count": 0}
        with patch("skill_poly_trader_v2.cli.build_status", return_value=status):
            with patch("sys.stdout.write") as mock_write:
                code = main(["status"])

        self.assertEqual(code, 0)
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("cash: 10000", written)

    def test_sync_tags_command_prints_yaml(self):
        report = {"tagIndexPath": "/tmp/tags.json", "count": 300}
        with patch("skill_poly_trader_v2.cli.sync_tags", return_value=report):
            with patch("sys.stdout.write") as mock_write:
                code = main(["sync-tags"])

        self.assertEqual(code, 0)
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("count: 300", written)

    def test_buy_command_calls_v2_engine(self):
        report = {"selected_trade": {"slug": "test-market", "outcome_name": "Yes"}}
        with patch("skill_poly_trader_v2.cli.buy_position", return_value=report) as mock_buy:
            with patch("sys.stdout.write") as mock_write:
                code = main(["buy", "--slug", "test-market", "--outcome-index", "0", "--probability", "0.6"])

        self.assertEqual(code, 0)
        mock_buy.assert_called_once_with(
            slug="test-market",
            outcome_index=0,
            probability=0.6,
            size=25.0,
            reason="Agent judged from external research",
            dry_run=False,
        )
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn('outcome_name: "Yes"', written)

    def test_sell_command_passes_reason(self):
        report = {"action": "SELL", "reason": "Edge reversed"}
        with patch("skill_poly_trader_v2.cli.sell_position", return_value=report) as mock_sell:
            with patch("sys.stdout.write"):
                code = main(["sell", "--slug", "test-market", "--reason", "Edge reversed"])

        self.assertEqual(code, 0)
        mock_sell.assert_called_once_with(slug="test-market", reason="Edge reversed")

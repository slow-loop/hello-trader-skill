from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch

import sys

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from skill_poly_trader.engine import (
    build_scan_report,
    build_status,
    close_position,
    decide_trade,
    decision_from_probability,
    initialize_ledger,
    load_ledger,
    record_agent_decision,
    run_cycle,
    snapshot_equity,
)
from skill_poly_trader.models import MarketSnapshot


def make_snapshot(**overrides) -> MarketSnapshot:
    base = {
        "market_id": "1",
        "slug": "test-market",
        "question": "Will test happen?",
        "yes_price": 0.20,
        "no_price": 0.80,
        "volume_24h": 200_000.0,
        "liquidity": 150_000.0,
        "one_day_price_change": 0.10,
        "best_bid": 0.19,
        "best_ask": 0.21,
        "end_date": None,
        "days_to_resolution": 10,
    }
    base.update(overrides)
    return MarketSnapshot(**base)


class EngineTests(unittest.TestCase):
    def test_decide_trade_places_buy_yes_for_positive_llm_edge(self):
        decision = decide_trade(make_snapshot(), probability_fn=lambda _: (0.35, "test-model"))

        self.assertEqual(decision.action, "BUY_YES")
        self.assertGreater(decision.edge, 0)
        self.assertEqual(decision.paper_size, 25.0)
        self.assertGreater(decision.shares, 0)

    def test_run_cycle_updates_ledger(self):
        tmp_path = Path(self._testMethodName)
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))

        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path)

        with patch("skill_poly_trader.engine.build_snapshots", return_value=[make_snapshot()]):
            result = run_cycle(ledger_path=ledger_path, probability_fn=lambda _: (0.35, "test-model"))

        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(result["qualified"], 1)
        self.assertEqual(result["selected_trade"]["action"], "BUY_YES")
        self.assertEqual(ledger["cash"], 9975.0)
        self.assertEqual(len(ledger["open_positions"]), 1)
        self.assertEqual(len(ledger["history"]), 1)

    def test_build_scan_report_returns_snapshot_payloads(self):
        events = [
            {
                "event_id": "evt-1",
                "slug": "test-event",
                "title": "Test Event",
                "category": "Politics",
                "end_date": None,
                "volume_24h": 100000.0,
                "volume": 250000.0,
                "liquidity": 150000.0,
                "market_count": 1,
                "markets": [make_snapshot()],
            }
        ]
        with patch("skill_poly_trader.engine.build_event_candidates", return_value=events):
            report = build_scan_report(limit=12, candidate_count=6)

        self.assertEqual(report["scanned"], 1)
        self.assertEqual(report["event_count"], 1)
        self.assertEqual(report["events"][0]["title"], "Test Event")
        self.assertEqual(report["events"][0]["markets"][0]["slug"], "test-market")
        self.assertNotIn("snapshots", report)

    def test_build_scan_report_drops_empty_events(self):
        events = [
            {
                "event_id": "evt-1",
                "slug": "has-markets",
                "title": "Has Markets",
                "category": "Politics",
                "end_date": None,
                "volume_24h": 100000.0,
                "volume": 250000.0,
                "liquidity": 150000.0,
                "market_count": 1,
                "markets": [make_snapshot()],
            },
            {
                "event_id": "evt-2",
                "slug": "no-markets",
                "title": "Multi Choice Event",
                "category": "Sports",
                "end_date": None,
                "volume_24h": 500000.0,
                "volume": 1000000.0,
                "liquidity": 300000.0,
                "market_count": 0,
                "markets": [],
            },
        ]
        with patch("skill_poly_trader.engine.build_event_candidates", return_value=events):
            report = build_scan_report(limit=12, candidate_count=6)

        self.assertEqual(report["event_count"], 1)
        self.assertEqual(report["scanned"], 1)
        self.assertEqual(report["events"][0]["title"], "Has Markets")

    def test_record_agent_decision_updates_ledger(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))

        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path)

        market_payload = {
            "id": "1",
            "slug": "test-market",
            "question": "Will test happen?",
            "outcomes": '["Yes","No"]',
            "outcomePrices": "[0.2,0.8]",
            "volume24hr": "200000",
            "liquidity": "150000",
            "bestBid": "0.19",
            "bestAsk": "0.21",
            "oneDayPriceChange": "0.1",
            "endDate": None,
        }
        with patch("skill_poly_trader.engine.fetch_market_by_slug", return_value=market_payload):
            result = record_agent_decision(slug="test-market", model_yes=0.35, ledger_path=ledger_path)

        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(result["selected_trade"]["action"], "BUY_YES")
        self.assertEqual(ledger["cash"], 9975.0)
        self.assertEqual(len(ledger["history"]), 1)

    def test_record_agent_decision_rejects_duplicate_open_position(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))

        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path)

        market_payload = {
            "id": "1",
            "slug": "test-market",
            "question": "Will test happen?",
            "outcomes": '["Yes","No"]',
            "outcomePrices": "[0.2,0.8]",
            "volume24hr": "200000",
            "liquidity": "150000",
            "bestBid": "0.19",
            "bestAsk": "0.21",
            "oneDayPriceChange": "0.1",
            "endDate": None,
        }

        with patch("skill_poly_trader.engine.fetch_market_by_slug", return_value=market_payload):
            record_agent_decision(slug="test-market", model_yes=0.35, ledger_path=ledger_path)
            with self.assertRaises(RuntimeError):
                record_agent_decision(slug="test-market", model_yes=0.35, ledger_path=ledger_path)


    def test_close_position_resolved_yes_wins(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))

        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path)

        # Open a position first
        with patch("skill_poly_trader.engine.build_snapshots", return_value=[make_snapshot()]):
            run_cycle(ledger_path=ledger_path, probability_fn=lambda _: (0.35, "test-model"))

        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(len(ledger["open_positions"]), 1)
        self.assertEqual(ledger["open_positions"][0]["side"], "YES")

        # Close: market resolved YES → we win
        result = close_position(slug="test-market", outcome="YES", ledger_path=ledger_path)
        self.assertEqual(result["outcome"], "YES")
        self.assertGreater(result["pnl"], 0)
        self.assertEqual(result["exit_price"], 1.0)

        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(len(ledger["open_positions"]), 0)
        self.assertEqual(len(ledger["history"]), 2)  # open + close

    def test_close_position_resolved_no_loses(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))

        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path)

        with patch("skill_poly_trader.engine.build_snapshots", return_value=[make_snapshot()]):
            run_cycle(ledger_path=ledger_path, probability_fn=lambda _: (0.35, "test-model"))

        # Close: market resolved NO → YES side loses
        result = close_position(slug="test-market", outcome="NO", ledger_path=ledger_path)
        self.assertEqual(result["outcome"], "NO")
        self.assertLess(result["pnl"], 0)
        self.assertEqual(result["exit_price"], 0.0)

        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(len(ledger["open_positions"]), 0)

    def test_close_position_sell_at_market(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))

        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path)

        with patch("skill_poly_trader.engine.build_snapshots", return_value=[make_snapshot()]):
            run_cycle(ledger_path=ledger_path, probability_fn=lambda _: (0.35, "test-model"))

        market_payload = {
            "id": "1", "slug": "test-market", "question": "Will test happen?",
            "outcomes": '["Yes","No"]', "outcomePrices": "[0.30,0.70]",
            "volume24hr": "200000", "liquidity": "150000",
            "bestBid": "0.29", "bestAsk": "0.31", "oneDayPriceChange": "0.1", "endDate": None,
        }
        with patch("skill_poly_trader.engine.fetch_market_by_slug", return_value=market_payload):
            result = close_position(slug="test-market", outcome="SELL", ledger_path=ledger_path)

        self.assertEqual(result["outcome"], "SELL")
        self.assertEqual(result["exit_price"], 0.30)

    def test_close_position_not_found_raises(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))

        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path)

        with self.assertRaises(RuntimeError):
            close_position(slug="nonexistent", outcome="YES", ledger_path=ledger_path)

    def test_insurance_model_lower_threshold(self):
        """Insurance model: NO >= 0.88 uses 3% edge threshold instead of 1.5%."""
        # YES=0.08, NO=0.92 → insurance zone
        snap = make_snapshot(yes_price=0.08, no_price=0.92)
        # model_yes=0.04 → edge_no = 0.96 - 0.92 = 0.04 (above 3%)
        decision = decision_from_probability(snap, model_yes=0.04, reason="test insurance")
        self.assertEqual(decision.action, "BUY_NO")
        self.assertIn("[insurance]", decision.reason)

    def test_insurance_model_rejects_below_3pct(self):
        """Insurance model: edge < 3% still rejected even in insurance zone."""
        snap = make_snapshot(yes_price=0.08, no_price=0.92)
        # model_yes=0.07 → edge_no = 0.93 - 0.92 = 0.01 (below 3%)
        decision = decision_from_probability(snap, model_yes=0.07, reason="test insurance")
        self.assertEqual(decision.action, "NO_TRADE")

    def test_normal_market_uses_standard_threshold(self):
        """Normal market (NO < 0.88) uses standard 1.5% threshold."""
        snap = make_snapshot(yes_price=0.40, no_price=0.60)
        # model_yes=0.37 → edge_no = 0.63 - 0.60 = 0.03
        # This passes standard 1.5% but is NOT insurance zone
        decision = decision_from_probability(snap, model_yes=0.37, reason="test normal")
        self.assertEqual(decision.action, "BUY_NO")
        self.assertNotIn("[insurance]", decision.reason)

    def test_snapshot_equity(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))

        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path)

        result = snapshot_equity(ledger_path=ledger_path)
        self.assertEqual(result["cash"], 10_000.0)
        self.assertEqual(result["equity"], 10_000.0)
        self.assertEqual(result["open_positions"], 0)

        curve_path = tmp_path / "equity_curve.json"
        self.assertTrue(curve_path.exists())
        curve = json.loads(curve_path.read_text(encoding="utf-8"))
        self.assertEqual(len(curve), 1)


    def test_initialize_ledger_exists_without_force_returns_early(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))

        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path, initial_cash=100)
        msg = initialize_ledger(ledger_path=ledger_path, initial_cash=200, force=False)
        self.assertIn("already exists", msg)
        
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(ledger["starting_cash"], 100.0)

    def test_initialize_ledger_exists_with_force_overwrites(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))

        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path, initial_cash=100)
        msg = initialize_ledger(ledger_path=ledger_path, initial_cash=200, force=True)
        self.assertIn("Initialized ledger", msg)
        
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(ledger["starting_cash"], 200.0)

    def test_load_ledger_auto_initializes(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))

        ledger_path = tmp_path / "ledger.json"
        # path doesn't exist yet
        ledger = load_ledger(ledger_path=ledger_path)
        self.assertEqual(ledger["starting_cash"], 10_000.0)
        self.assertTrue(ledger_path.exists())

    def test_decision_filters_volume_liquidity_spread(self):
        # 1. Volume too low (< 50,000)
        snap = make_snapshot(volume_24h=1000.0)
        decision = decision_from_probability(snap, model_yes=0.35, reason="test")
        self.assertEqual(decision.action, "NO_TRADE")
        self.assertIn("volume below floor", decision.reason)

        # 2. Liquidity too low (< 50,000)
        snap = make_snapshot(liquidity=1000.0)
        decision = decision_from_probability(snap, model_yes=0.35, reason="test")
        self.assertEqual(decision.action, "NO_TRADE")
        self.assertIn("liquidity below floor", decision.reason)

        # 3. Spread too wide (> 0.08)
        # yes_price=0.20 (so best_bid around 0.19, best_ask around 0.28)
        snap = make_snapshot(best_bid=0.15, best_ask=0.25) # spread 0.10
        decision = decision_from_probability(snap, model_yes=0.35, reason="test")
        self.assertEqual(decision.action, "NO_TRADE")
        self.assertIn("spread too wide", decision.reason)

    def test_run_cycle_insufficient_cash_does_not_trade(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))
        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path, initial_cash=10.0) # only $10

        # paper_size is 25.0
        with patch("skill_poly_trader.engine.build_snapshots", return_value=[make_snapshot()]):
            result = run_cycle(ledger_path=ledger_path, probability_fn=lambda _: (0.35, "test-model"))

        self.assertEqual(result["qualified"], 1)
        self.assertIsNone(result["trade_record"])
        self.assertEqual(len(result["decision_log"]), 1)
        
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(ledger["cash"], 10.0)
        self.assertEqual(len(ledger["open_positions"]), 0)

    def test_run_cycle_no_candidates(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))
        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path)

        # No snapshots returned
        with patch("skill_poly_trader.engine.build_snapshots", return_value=[]):
            result = run_cycle(ledger_path=ledger_path, probability_fn=lambda _: (0.35, "test-model"))

        self.assertEqual(result["scanned"], 0)
        self.assertIsNone(result["selected_trade"])

    def test_close_position_invalid_outcome_raises(self):
        with self.assertRaises(ValueError):
            close_position(slug="any", outcome="INVALID")

    def test_close_position_sell_fetch_failure(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))
        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path)

        # Open a position
        with patch("skill_poly_trader.engine.build_snapshots", return_value=[make_snapshot()]):
            run_cycle(ledger_path=ledger_path, probability_fn=lambda _: (0.35, "test-model"))

        # Try to close with SELL but fetch fails
        with patch("skill_poly_trader.engine.fetch_market_by_slug", return_value=None):
            with self.assertRaises(RuntimeError) as exc:
                close_position(slug="test-market", outcome="SELL", ledger_path=ledger_path)
            self.assertIn("Cannot fetch current price", str(exc.exception))

    def test_build_status_calculates_pnl_correctly(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))
        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path)

        # Open a position: YES at 0.20 (shares = 25 / 0.2 = 125)
        with patch("skill_poly_trader.engine.build_snapshots", return_value=[make_snapshot(yes_price=0.20)]):
            run_cycle(ledger_path=ledger_path, probability_fn=lambda _: (0.35, "test-model"), paper_size=25.0)

        # Currect price is now 0.40 -> value = 125 * 0.4 = 50.0. Cost was 25.0. PNL = 25.0.
        market_payload = {
            "id": "1", "slug": "test-market", "question": "Will test happen?",
            "outcomes": '["Yes","No"]', "outcomePrices": "[0.40,0.60]", # YES=0.40
            "volume24hr": "200000", "liquidity": "150000",
            "bestBid": "0.39", "bestAsk": "0.41", "oneDayPriceChange": "0.1", "endDate": None,
        }
        with patch("skill_poly_trader.engine.fetch_market_by_slug", return_value=market_payload):
            status = build_status(ledger_path=ledger_path)

        self.assertEqual(status["open_positions"][0]["current_value"], 50.0)
        self.assertEqual(status["open_positions"][0]["pnl"], 25.0)
        self.assertEqual(status["equity_estimate"], 9975.0 + 50.0) # remaining cash + current value

    def test_build_status_handles_fetch_error_silently(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))
        ledger_path = tmp_path / "ledger.json"
        initialize_ledger(ledger_path=ledger_path)

        with patch("skill_poly_trader.engine.build_snapshots", return_value=[make_snapshot()]):
            run_cycle(ledger_path=ledger_path, probability_fn=lambda _: (0.35, "test-model"))

        # Fetch fails -> should fall back to cost basis
        with patch("skill_poly_trader.engine.fetch_market_by_slug", side_effect=ValueError("failing")):
            status = build_status(ledger_path=ledger_path)
            
        self.assertEqual(status["open_positions"][0]["current_value"], 25.0)
        self.assertEqual(status["open_positions"][0]["pnl"], 0.0)


def _cleanup_tmp(path: Path) -> None:
    if not path.exists():
        return
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    path.rmdir()

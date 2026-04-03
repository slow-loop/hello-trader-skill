from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import patch

import sys

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from skill_poly_trader_v2.api import build_market_detail, build_market_summary, derive_terminal_payoffs, is_candidate_market
from skill_poly_trader_v2.engine import build_markets_report, build_status, buy_position, initialize_ledger, load_ledger, sell_position, sync_tags
from skill_poly_trader_v2.profiles import resolve_profile_stages


def make_market(**overrides):
    near_end = (datetime.now(timezone.utc) + timedelta(days=10)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    base = {
        "id": "market-1",
        "question": "Will test happen?",
        "slug": "test-market",
        "description": "Test market description",
        "outcomes": '["Yes","No"]',
        "outcomePrices": "[0.40,0.60]",
        "endDate": near_end,
        "volume24hr": "100000",
        "liquidity": "75000",
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "bestBid": "0.39",
        "bestAsk": "0.41",
        "spread": "0.02",
        "lastTradePrice": "0.40",
        "updatedAt": updated_at,
        "resolutionSource": "",
        "events": [{"title": "Test Event", "slug": "test-event", "category": "Politics", "description": "Event desc", "openInterest": "1234", "endDate": near_end}],
    }
    base.update(overrides)
    return base


def make_event(*, event_id: str = "event-1", title: str = "Test Event", tags: list[str] | None = None, markets: list[dict[str, object]] | None = None, **overrides):
    near_end = (datetime.now(timezone.utc) + timedelta(days=10)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    base = {
        "id": event_id,
        "slug": f"{event_id}-slug",
        "title": title,
        "description": "Event description",
        "endDate": near_end,
        "tags": [{"slug": slug} for slug in (tags or [])],
        "markets": markets or [make_market()],
    }
    base.update(overrides)
    return base


class EngineV2Tests(unittest.TestCase):
    def test_market_summary_uses_api_names(self):
        summary = build_market_summary(make_market())
        self.assertEqual(summary["question"], "Will test happen?")
        self.assertEqual(summary["outcomes"], ["Yes", "No"])
        self.assertEqual(summary["outcomePrices"], [0.40, 0.60])
        self.assertNotIn("market_yes", summary)

    def test_candidate_filter_accepts_simple_binary_market(self):
        self.assertTrue(is_candidate_market(make_market()))

    def test_candidate_filter_rejects_closed_market(self):
        self.assertFalse(is_candidate_market(make_market(closed=True)))

    def test_build_markets_report_discovers_from_events_then_limits(self):
        stage_pages = {
            "all-updatedAt": [make_event(event_id="event-1", markets=[make_market(slug="keep-1")])],
            "all-endDate": [make_event(event_id="event-2", markets=[make_market(slug="keep-2")])],
        }

        def fetch_side_effect(*, order=None, **_kwargs):
            if order == "updatedAt":
                return stage_pages["all-updatedAt"]
            return stage_pages["all-endDate"]

        with patch(
            "skill_poly_trader_v2.discovery.resolve_profile_stages",
            return_value=[
                {"name": "all-updatedAt", "params": {"order": "updatedAt"}},
                {"name": "all-endDate", "params": {"order": "endDate"}},
            ],
        ):
            with patch("skill_poly_trader_v2.discovery.fetch_events_page", side_effect=fetch_side_effect):
                report = build_markets_report(limit=2, profile_name="all")

        self.assertEqual(report["count"], 2)
        self.assertEqual(report["profile"], "all")
        self.assertEqual(report["limit"], 2)
        self.assertEqual({item["slug"] for item in report["markets"]}, {"keep-1", "keep-2"})

    def test_geo_profile_resolves_to_native_event_queries(self):
        with patch("skill_poly_trader_v2.profiles.resolve_tag_ids", return_value=[1, 2, 3]):
            stages = resolve_profile_stages("geo")

        self.assertEqual(len(stages), 3)
        self.assertEqual(stages[0]["params"]["tag_slug"], "politics")
        self.assertEqual(stages[0]["params"]["order"], "endDate")
        self.assertEqual(stages[1]["params"]["order"], "updatedAt")
        self.assertEqual(stages[2]["params"]["order"], "createdAt")
        self.assertEqual(stages[0]["params"]["exclude_tag_id"], [1, 2, 3])
        self.assertIn("end_date_max", stages[0]["params"])

    def test_geo_scan_preserves_unique_markets_across_buckets(self):
        def fetch_side_effect(*, order=None, **_kwargs):
            if order == "endDate":
                return [
                    make_event(
                        event_id="event-end",
                        markets=[
                            make_market(slug="end-1", question="End 1", volume24hr="90000"),
                            make_market(slug="shared", question="Shared", volume24hr="120000"),
                        ],
                    )
                ]
            if order == "updatedAt":
                return [
                    make_event(
                        event_id="event-updated",
                        markets=[
                            make_market(slug="shared", question="Shared"),
                            make_market(slug="updated-1", question="Updated 1"),
                        ],
                    )
                ]
            return [
                make_event(
                    event_id="event-created",
                    markets=[make_market(slug="created-1", question="Created 1")],
                )
            ]

        with patch(
            "skill_poly_trader_v2.discovery.resolve_profile_stages",
            return_value=[
                {"name": "geo-endDate", "params": {"order": "endDate"}},
                {"name": "geo-updatedAt", "params": {"order": "updatedAt"}},
                {"name": "geo-createdAt", "params": {"order": "createdAt"}},
            ],
        ):
            with patch("skill_poly_trader_v2.discovery.fetch_events_page", side_effect=fetch_side_effect):
                report = build_markets_report(limit=3, profile_name="geo")

        self.assertEqual([item["slug"] for item in report["markets"]], ["shared", "updated-1", "created-1"])

    def test_sports_profile_resolves_to_freshness_first_event_queries(self):
        stages = resolve_profile_stages("sports")

        self.assertEqual(len(stages), 3)
        self.assertEqual(stages[0]["params"]["order"], "updatedAt")
        self.assertEqual(stages[1]["params"]["order"], "createdAt")
        self.assertEqual(stages[2]["params"]["order"], "endDate")
        self.assertIn("end_date_max", stages[0]["params"])

    def test_sports_scan_preserves_freshness_buckets(self):
        def fetch_side_effect(*, order=None, **_kwargs):
            if order == "updatedAt":
                return [
                    make_event(
                        event_id="sports-updated",
                        tags=["sports"],
                        markets=[
                            make_market(slug="shared-sports", question="Shared Sports", volume24hr="110000"),
                            make_market(slug="updated-sports", question="Updated Sports", volume24hr="90000"),
                        ],
                    )
                ]
            if order == "createdAt":
                return [
                    make_event(
                        event_id="sports-created",
                        tags=["sports"],
                        markets=[
                            make_market(slug="shared-sports", question="Shared Sports"),
                            make_market(slug="created-sports", question="Created Sports"),
                        ],
                    )
                ]
            return [
                make_event(
                    event_id="sports-end",
                    tags=["sports"],
                    markets=[make_market(slug="end-sports", question="End Sports")],
                )
            ]

        with patch(
            "skill_poly_trader_v2.discovery.resolve_profile_stages",
            return_value=[
                {"name": "sports-updatedAt", "params": {"order": "updatedAt"}},
                {"name": "sports-createdAt", "params": {"order": "createdAt"}},
                {"name": "sports-endDate", "params": {"order": "endDate"}},
            ],
        ):
            with patch("skill_poly_trader_v2.discovery.fetch_events_page", side_effect=fetch_side_effect):
                report = build_markets_report(limit=3, profile_name="sports")

        self.assertEqual([item["slug"] for item in report["markets"]], ["shared-sports", "created-sports", "end-sports"])

    def test_sports_profile_excludes_same_day_markets(self):
        same_day_end = (datetime.now(timezone.utc) + timedelta(hours=8)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        next_day_end = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        page = [
            make_event(
                event_id="sports-window",
                tags=["sports"],
                markets=[
                    make_market(slug="same-day-sports", endDate=same_day_end, volume24hr="90000"),
                    make_market(slug="next-day-sports", endDate=next_day_end, volume24hr="80000"),
                ],
            )
        ]

        with patch("skill_poly_trader_v2.discovery.resolve_profile_stages", return_value=[{"name": "sports-updatedAt", "params": {"order": "updatedAt"}}]):
            with patch("skill_poly_trader_v2.discovery.fetch_events_page", return_value=page):
                report = build_markets_report(limit=5, profile_name="sports")

        self.assertEqual([item["slug"] for item in report["markets"]], ["next-day-sports"])

    def test_sports_profile_excludes_esports_and_qualification_text(self):
        page = [
            make_event(
                event_id="sports-mixed",
                tags=["sports"],
                title="Mixed sports event",
                markets=[
                    make_market(slug="esports-market", question="Counter-Strike: paiN vs 9z", volume24hr="90000"),
                    make_market(slug="qualification-market", question="Qualification: Player A vs Player B", volume24hr="85000"),
                    make_market(slug="plain-sports", question="Celtics vs. Hawks", volume24hr="80000"),
                ],
            )
        ]

        with patch("skill_poly_trader_v2.discovery.resolve_profile_stages", return_value=[{"name": "sports-updatedAt", "params": {"order": "updatedAt"}}]):
            with patch("skill_poly_trader_v2.discovery.fetch_events_page", return_value=page):
                report = build_markets_report(limit=5, profile_name="sports")

        self.assertEqual([item["slug"] for item in report["markets"]], ["plain-sports"])

    def test_build_markets_report_excludes_open_positions(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))
        ledger_path = tmp_path / "ledger_v2.json"
        ledger = {
            "version": 2,
            "starting_cash": 10000.0,
            "cash": 10000.0,
            "open_positions": [{"slug": "keep-1"}],
            "history": [],
            "last_run_at": None,
        }
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

        page = [make_event(event_id="event-1", markets=[make_market(slug="keep-1"), make_market(slug="keep-2")])]
        with patch("skill_poly_trader_v2.discovery.resolve_profile_stages", return_value=[{"name": "all-updatedAt", "params": {}}]):
            with patch("skill_poly_trader_v2.discovery.fetch_events_page", return_value=page):
                report = build_markets_report(limit=5, profile_name="all", ledger_path=ledger_path)

        self.assertEqual([item["slug"] for item in report["markets"]], ["keep-2"])

    def test_market_level_gates_exclude_thin_market_even_if_event_passes(self):
        thin_market = make_market(slug="thin", liquidity="5000", volume24hr="10")
        strong_market = make_market(slug="strong", liquidity="75000", volume24hr="100000")
        page = [make_event(event_id="event-1", markets=[thin_market, strong_market], liquidity="100000", volume24hr="100000")]

        with patch("skill_poly_trader_v2.discovery.resolve_profile_stages", return_value=[{"name": "all-updatedAt", "params": {}}]):
            with patch("skill_poly_trader_v2.discovery.fetch_events_page", return_value=page):
                report = build_markets_report(limit=5, profile_name="all")

        self.assertEqual([item["slug"] for item in report["markets"]], ["strong"])

    def test_days_to_resolution_falls_back_to_event_end_date(self):
        market_without_end = make_market(slug="no-end", endDate=None)
        event_end = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        page = [make_event(event_id="event-1", endDate=event_end, markets=[market_without_end])]

        with patch("skill_poly_trader_v2.discovery.resolve_profile_stages", return_value=[{"name": "all-endDate", "params": {}}]):
            with patch("skill_poly_trader_v2.discovery.fetch_events_page", return_value=page):
                report = build_markets_report(limit=5, profile_name="all")

        self.assertEqual(report["markets"][0]["endDate"], event_end)
        self.assertEqual(report["markets"][0]["daysToResolution"], 2)

    def test_default_profiles_exclude_family_markets(self):
        family_market = make_market(
            slug="bucket-market",
            question="Will the total number of TSA passengers be between 2,800,000 and 3,000,000?",
        )
        plain_market = make_market(slug="plain-market", question="Will Iran ceasefire by April 30?")
        page = [
            make_event(event_id="family-event", tags=["economy"], title="TSA passengers for March 29", markets=[family_market]),
            make_event(event_id="plain-event", tags=["economy"], title="Iran ceasefire", markets=[plain_market]),
        ]

        with patch("skill_poly_trader_v2.discovery.resolve_profile_stages", return_value=[{"name": "all-endDate", "params": {}}]):
            with patch("skill_poly_trader_v2.discovery.fetch_events_page", return_value=page):
                report = build_markets_report(limit=5, profile_name="all")

        self.assertEqual([item["slug"] for item in report["markets"]], ["plain-market"])
        self.assertFalse(report["markets"][0]["familyMarket"])

    def test_profiles_exclude_company_ranking_families(self):
        ranking_market = make_market(
            slug="ranking-market",
            question="Will DeepSeek have the best AI model at the end of April 2026?",
        )
        plain_market = make_market(slug="release-market", question="Will Claude 5 be released by April 30?")
        page = [
            make_event(
                event_id="ranking-event",
                title="Which company has best AI model end of April?",
                markets=[ranking_market, make_market(slug="alt-1"), make_market(slug="alt-2"), make_market(slug="alt-3")],
            ),
            make_event(event_id="plain-event", title="Claude 5 released by April?", markets=[plain_market]),
        ]

        with patch("skill_poly_trader_v2.discovery.resolve_profile_stages", return_value=[{"name": "ai-updatedAt", "params": {}}]):
            with patch("skill_poly_trader_v2.discovery.fetch_events_page", return_value=page):
                report = build_markets_report(limit=5, profile_name="ai")

        self.assertEqual([item["slug"] for item in report["markets"]], ["release-market"])

    def test_sports_profile_excludes_derivative_and_keeps_one_market_per_event(self):
        page = [
            make_event(
                event_id="sports-event",
                tags=["sports"],
                markets=[
                    make_market(slug="moneyline", question="Lakers vs. Celtics", outcomes='["Lakers","Celtics"]', volume24hr="90000"),
                    make_market(slug="spread", question="Spread: Celtics (-5.5)", outcomes='["Celtics","Lakers"]', volume24hr="120000"),
                    make_market(slug="total", question="Lakers vs. Celtics: O/U 228.5", outcomes='["Over","Under"]', volume24hr="80000"),
                ],
            )
        ]

        with patch("skill_poly_trader_v2.discovery.resolve_profile_stages", return_value=[{"name": "sports-endDate", "params": {}}]):
            with patch("skill_poly_trader_v2.discovery.fetch_events_page", return_value=page):
                report = build_markets_report(limit=5, profile_name="sports")

        self.assertEqual([item["slug"] for item in report["markets"]], ["moneyline"])

    def test_negative_days_market_is_excluded_after_end_date_fallback(self):
        past_end = (datetime.now(timezone.utc) - timedelta(days=3)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        page = [make_event(event_id="event-1", endDate=past_end, markets=[make_market(slug="stale", endDate=None)])]

        with patch("skill_poly_trader_v2.discovery.resolve_profile_stages", return_value=[{"name": "all-endDate", "params": {}}]):
            with patch("skill_poly_trader_v2.discovery.fetch_events_page", return_value=page):
                report = build_markets_report(limit=5, profile_name="all")

        self.assertEqual(report["markets"], [])

    def test_market_detail_includes_deeper_fields(self):
        detail = build_market_detail({**make_market(), "eventTags": ["politics", "world"]})
        self.assertEqual(detail["bestBid"], 0.39)
        self.assertEqual(detail["events"][0]["title"], "Test Event")
        self.assertIn("resolutionSource", detail)
        self.assertEqual(detail["outcomeIndexMap"], {"0": "Yes", "1": "No"})
        self.assertEqual(detail["eventTags"], ["politics", "world"])

    def test_buy_position_uses_outcome_index(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))
        ledger_path = tmp_path / "ledger_v2.json"
        initialize_ledger(ledger_path=ledger_path)

        with patch("skill_poly_trader_v2.engine.fetch_market_detail", return_value=build_market_detail(make_market())):
            result = buy_position(
                slug="test-market",
                outcome_index=1,
                probability=0.70,
                ledger_path=ledger_path,
            )

        ledger = load_ledger(ledger_path=ledger_path)
        self.assertEqual(result["selected_trade"]["outcome_name"], "No")
        self.assertEqual(ledger["open_positions"][0]["outcome_index"], 1)
        self.assertEqual(ledger["cash"], 9975.0)

    def test_sell_position_uses_current_outcome_price(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))
        ledger_path = tmp_path / "ledger_v2.json"
        initialize_ledger(ledger_path=ledger_path)

        with patch("skill_poly_trader_v2.engine.fetch_market_detail", return_value=build_market_detail(make_market(outcomePrices="[0.40,0.60]"))):
            buy_position(slug="test-market", outcome_index=0, ledger_path=ledger_path)

        with patch("skill_poly_trader_v2.engine.fetch_market_detail", return_value=build_market_detail(make_market(outcomePrices="[0.55,0.45]"))):
            result = sell_position(slug="test-market", reason="Edge disappeared", ledger_path=ledger_path)

        ledger = load_ledger(ledger_path=ledger_path)
        self.assertEqual(result["action"], "SELL")
        self.assertEqual(result["exit_price"], 0.55)
        self.assertEqual(result["reason"], "Edge disappeared")
        self.assertEqual(result["exit_type"], "MANUAL_SELL")
        self.assertEqual(ledger["last_run_at"], result["timestamp"])

    def test_status_auto_settles_when_terminal_payoff_is_available(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))
        ledger_path = tmp_path / "ledger_v2.json"
        initialize_ledger(ledger_path=ledger_path)

        with patch("skill_poly_trader_v2.engine.fetch_market_detail", return_value=build_market_detail(make_market(outcomePrices="[0.40,0.60]"))):
            buy_position(slug="test-market", outcome_index=0, ledger_path=ledger_path)

        closed_market = make_market(closed=True, outcomePrices="[1,0]")
        with patch("skill_poly_trader_v2.engine.fetch_market_by_slug", return_value=closed_market):
            status = build_status(ledger_path=ledger_path)

        ledger = load_ledger(ledger_path=ledger_path)
        self.assertEqual(len(status["auto_settled"]), 1)
        self.assertEqual(status["auto_settled"][0]["exit_price"], 1.0)
        self.assertEqual(status["auto_settled"][0]["exit_type"], "AUTO_SETTLE")
        self.assertEqual(len(status["open_positions"]), 0)
        self.assertEqual(ledger["last_run_at"], status["auto_settled"][0]["timestamp"])

    def test_status_marks_closed_pending_when_api_lacks_terminal_payoff(self):
        tmp_path = Path(f"{self._testMethodName}_tmp")
        tmp_path.mkdir(exist_ok=True)
        self.addCleanup(lambda: _cleanup_tmp(tmp_path))
        ledger_path = tmp_path / "ledger_v2.json"
        initialize_ledger(ledger_path=ledger_path)

        with patch("skill_poly_trader_v2.engine.fetch_market_detail", return_value=build_market_detail(make_market(outcomePrices="[0.40,0.60]"))):
            buy_position(slug="test-market", outcome_index=0, ledger_path=ledger_path)

        closed_market = make_market(closed=True, outcomePrices="[0,0]")
        with patch("skill_poly_trader_v2.engine.fetch_market_by_slug", return_value=closed_market):
            with patch("skill_poly_trader_v2.engine.fetch_market_detail", return_value=build_market_detail(closed_market)):
                status = build_status(ledger_path=ledger_path)

        self.assertEqual(len(status["auto_settled"]), 0)
        self.assertEqual(len(status["closed_pending"]), 1)
        self.assertEqual(status["open_positions"][0]["market_state"], "CLOSED_PENDING")

    def test_terminal_payoffs_require_clean_zero_one_vector(self):
        self.assertEqual(derive_terminal_payoffs(make_market(closed=True, outcomePrices="[1,0]")), [1.0, 0.0])

    def test_sync_tags_returns_summary(self):
        with patch("skill_poly_trader_v2.tags.sync_tag_index", return_value={"fetchedAt": "2026-03-29T00:00:00Z", "count": 300}):
            result = sync_tags()

        self.assertEqual(result["count"], 300)
        self.assertIn("tags.json", result["tagIndexPath"])

    def test_terminal_payoffs_reject_non_terminal_vector(self):
        self.assertIsNone(derive_terminal_payoffs(make_market(closed=True, outcomePrices="[0,0]")))


def _cleanup_tmp(path: Path) -> None:
    if not path.exists():
        return
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    path.rmdir()

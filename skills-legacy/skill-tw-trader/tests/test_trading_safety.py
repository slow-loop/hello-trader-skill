import unittest
from unittest.mock import patch, MagicMock
from skill_tw_trader.core.trading_engine import (
    validate_order,
    execute_order,
    check_pending_orders,
    update_orders,
    SpotPrice
)

class TestTradingSafety(unittest.TestCase):
    def setUp(self):
        # Default mock spot price
        self.mock_spot = SpotPrice(
            price=100.0,
            prev_close=100.0,
            source="mock"
        )

    def test_validate_order_limit_up(self):
        # Limit up is 100 * 1.1 = 110
        spot = SpotPrice(price=110.0, prev_close=100.0, source="mock")
        # Buy at limit up price
        ok, reason, fill_price = validate_order("2330.TW", "BUY", 110.0, spot)
        # Should be rejected because it's locked at limit up
        self.assertFalse(ok)
        self.assertIn("locked at limit-up", reason)

    def test_validate_order_limit_down(self):
        # Limit down is 100 * 0.9 = 90
        spot = SpotPrice(price=90.0, prev_close=100.0, source="mock")
        # Sell at limit down price
        ok, reason, fill_price = validate_order("2330.TW", "SELL", 90.0, spot)
        # Should be rejected because it's locked at limit down
        self.assertFalse(ok)
        self.assertIn("locked at limit-down", reason)

    def test_validate_order_price_deviation(self):
        # Price is 100.0, deviation is 2%
        spot = SpotPrice(price=100.0, prev_close=100.0, source="mock")
        # Buy at 105.0 (5% deviation)
        ok, reason, fill_price = validate_order("2330.TW", "BUY", 105.0, spot)
        self.assertFalse(ok)
        self.assertIn("deviates", reason)

    @patch("skill_tw_trader.core.trading_engine.get_twse_market_session")
    @patch("skill_tw_trader.core.trading_engine.get_spot_price")
    def test_execute_order_market_closed(self, mock_get_spot, mock_get_session):
        mock_get_session.return_value = "closed"
        mock_get_spot.return_value = self.mock_spot
        
        result = execute_order("2330.TW", "BUY", 100, price=100.0, stop_loss=90.0, reason="Test")
        self.assertIn("Market is closed today", result)

    @patch("skill_tw_trader.core.trading_engine.get_twse_market_session")
    @patch("skill_tw_trader.core.trading_engine.get_spot_price")
    @patch("skill_tw_trader.core.trading_engine._load_ledger")
    def test_execute_order_insufficient_funds(self, mock_load, mock_get_spot, mock_get_session):
        mock_get_session.return_value = "market_open"
        mock_get_spot.return_value = self.mock_spot
        mock_load.return_value = {
            "cash": 100.0,
            "realized_pnl": 0.0,
            "positions": {},
            "orders": {},
            "trade_history": []
        }
        
        result = execute_order("2330.TW", "BUY", 1000, price=100.0, stop_loss=90.0, reason="Test")
        self.assertIn("Insufficient funds", result)

    @patch("skill_tw_trader.core.trading_engine._load_ledger")
    @patch("skill_tw_trader.core.trading_engine._save_ledger")
    def test_pending_orders_trigger_stop_loss(self, mock_save, mock_load):
        mock_load.return_value = {
            "cash": 100000.0,
            "realized_pnl": 0.0,
            "positions": {
                "2330.TW": {"shares": 1000, "avg_price": 100.0, "reason": "Test", "entry_date": "2026-03-25"}
            },
            "orders": {"2330.TW": {"stop_loss": 95.0}},
            "trade_history": []
        }
        
        current_prices = {"2330.TW": 94.0}
        executed = check_pending_orders(current_prices)
        
        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0]["type"], "stop_loss")
        self.assertEqual(executed[0]["price"], 94.0)
        self.assertTrue(mock_save.called)

    @patch("skill_tw_trader.core.trading_engine._load_ledger")
    @patch("skill_tw_trader.core.trading_engine._save_ledger")
    def test_pending_orders_trigger_take_profit(self, mock_save, mock_load):
        mock_load.return_value = {
            "cash": 100000.0,
            "realized_pnl": 0.0,
            "positions": {
                "2330.TW": {"shares": 1000, "avg_price": 100.0, "reason": "Test", "entry_date": "2026-03-25"}
            },
            "orders": {"2330.TW": {"take_profit": 110.0}},
            "trade_history": []
        }
        
        current_prices = {"2330.TW": 111.0}
        executed = check_pending_orders(current_prices)
        
        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0]["type"], "take_profit")
        self.assertEqual(executed[0]["price"], 111.0)
        self.assertTrue(mock_save.called)

    @patch("skill_tw_trader.core.trading_engine._load_ledger")
    @patch("skill_tw_trader.core.trading_engine._save_ledger")
    def test_update_orders(self, mock_save, mock_load):
        mock_load.return_value = {
            "positions": {"2330.TW": {"shares": 100, "avg_price": 100.0}},
            "orders": {}
        }
        
        result = update_orders("2330.TW", stop_loss=92.0, take_profit=115.0)
        self.assertIn("Updated 2330.TW", result)
        self.assertTrue(mock_save.called)
        
        saved_data = mock_save.call_args[0][0]
        self.assertEqual(saved_data["orders"]["2330.TW"]["stop_loss"], 92.0)
        self.assertEqual(saved_data["orders"]["2330.TW"]["take_profit"], 115.0)

if __name__ == "__main__":
    unittest.main()

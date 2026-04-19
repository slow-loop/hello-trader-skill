"""Binance Futures trader with testnet support.

Uses python-binance for order management. Testnet flag is controlled by config.
OI/gainers signals are always read from production endpoints (testnet has no live data).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

log = logging.getLogger(__name__)


@dataclass
class TradeResult:
    symbol: str
    side: str
    entry_price: float
    quantity: float
    order_id: str
    stop_loss_order_id: str
    timestamp: str
    testnet: bool
    dry_run: bool = False

    def to_dict(self) -> dict:
        return self.__dict__


class BinanceTrader:
    """Wraps python-binance client with fixed-loss stop (Lana's 200 USDT rule)."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        max_loss_usdt: float = 200.0,
        leverage: int = 10,
        dry_run: bool = False,
    ) -> None:
        self.testnet = testnet
        self.max_loss_usdt = max_loss_usdt
        self.leverage = leverage
        self.dry_run = dry_run

        if not dry_run:
            from binance.client import Client
            self._client = Client(
                api_key,
                api_secret,
                testnet=testnet,
            )
            if testnet:
                # python-binance uses different base URL for futures testnet
                self._client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"

    def _get_price(self, symbol: str) -> float:
        ticker = self._client.futures_symbol_ticker(symbol=symbol)
        return float(ticker["price"])

    def _calc_stop_price(self, entry: float, quantity: float, side: str) -> float:
        """Calculate stop price that limits loss to max_loss_usdt."""
        # loss = quantity * |entry - stop| * leverage (approximately)
        stop_gap = self.max_loss_usdt / (quantity * self.leverage)
        if side == "BUY":
            return round(entry - stop_gap, 4)
        else:
            return round(entry + stop_gap, 4)

    def _qty_precision(self, symbol: str) -> int:
        """Fetch quantityPrecision for symbol from exchangeInfo (cached per trader instance)."""
        if not hasattr(self, "_qty_precision_cache"):
            self._qty_precision_cache: dict[str, int] = {}
        if symbol not in self._qty_precision_cache:
            info = self._client.futures_exchange_info()
            for s in info.get("symbols", []):
                self._qty_precision_cache[s["symbol"]] = s.get("quantityPrecision", 3)
        return self._qty_precision_cache.get(symbol, 3)

    def _calc_quantity(self, symbol: str, balance_usdt: float, position_size_pct: float) -> float:
        price = self._get_price(symbol)
        notional = balance_usdt * position_size_pct * self.leverage
        qty = notional / price
        precision = self._qty_precision(symbol)
        return round(qty, precision)

    def open_long(
        self,
        symbol: str,
        position_size_pct: float = 0.05,
    ) -> TradeResult:
        ts = datetime.now(timezone.utc).isoformat()

        if self.dry_run:
            log.info("[DRY RUN] Would open LONG %s", symbol)
            return TradeResult(
                symbol=symbol,
                side="BUY",
                entry_price=0.0,
                quantity=0.0,
                order_id="dry-run",
                stop_loss_order_id="dry-run",
                timestamp=ts,
                testnet=self.testnet,
                dry_run=True,
            )

        # set leverage
        self._client.futures_change_leverage(symbol=symbol, leverage=self.leverage)

        # get available balance
        account = self._client.futures_account_balance()
        usdt_balance = next(
            (float(b["balance"]) for b in account if b["asset"] == "USDT"), 0.0
        )

        qty = self._calc_quantity(symbol, usdt_balance, position_size_pct)
        entry_price = self._get_price(symbol)

        # market order
        order = self._client.futures_create_order(
            symbol=symbol,
            side="BUY",
            type="MARKET",
            quantity=qty,
        )
        order_id = str(order["orderId"])
        log.info("Opened LONG %s qty=%s orderId=%s", symbol, qty, order_id)

        # stop-loss (closePosition=True so Binance auto-closes full position)
        stop_price = self._calc_stop_price(entry_price, qty, "BUY")
        sl_order = self._client.futures_create_order(
            symbol=symbol,
            side="SELL",
            type="STOP_MARKET",
            stopPrice=stop_price,
            closePosition=True,
        )
        # closePosition orders return algoId, not orderId
        sl_order_id = str(sl_order.get("orderId") or sl_order.get("algoId", "unknown"))
        log.info("Set stop-loss %s stopPrice=%s id=%s", symbol, stop_price, sl_order_id)

        return TradeResult(
            symbol=symbol,
            side="BUY",
            entry_price=entry_price,
            quantity=qty,
            order_id=order_id,
            stop_loss_order_id=sl_order_id,
            timestamp=ts,
            testnet=self.testnet,
        )

    def assess_position(self, symbol: str) -> dict:
        """Return current position info for the 15-min cron check."""
        if self.dry_run:
            return {"symbol": symbol, "dry_run": True}

        positions = self._client.futures_position_information(symbol=symbol)
        if not positions:
            return {"symbol": symbol, "error": "no position found"}
        pos = positions[0]
        return {
            "symbol": symbol,
            "entry_price": float(pos["entryPrice"]),
            "unrealized_pnl": float(pos["unRealizedProfit"]),
            "position_amt": float(pos["positionAmt"]),
            "mark_price": float(pos.get("markPrice", 0)),
        }

    def close_position(self, symbol: str, quantity: float) -> dict:
        """Partial close — Lana style: 1-5% at a time."""
        if self.dry_run:
            log.info("[DRY RUN] Would close %s qty=%s", symbol, quantity)
            return {"symbol": symbol, "dry_run": True}

        order = self._client.futures_create_order(
            symbol=symbol,
            side="SELL",
            type="MARKET",
            quantity=quantity,
            reduceOnly=True,
        )
        log.info("Partial close %s qty=%s orderId=%s", symbol, quantity, order["orderId"])
        return {"symbol": symbol, "order_id": str(order["orderId"]), "quantity": quantity}

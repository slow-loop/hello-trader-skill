"""
routes.py — FastAPI routes.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import database as db
from backend import services


def create_app() -> FastAPI:
    app = FastAPI(title="TW Trader API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Portfolio ─────────────────────────────────────────────────────────────

    @app.get("/api/agents/{agent_id}/portfolio")
    async def get_portfolio(agent_id: str):
        try:
            return await services.get_portfolio(agent_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/agents/{agent_id}/portfolio/equity")
    async def get_equity(agent_id: str, days: int = 90):
        return await db.get_equity_snapshots(agent_id, days=days)

    # ── Trades ────────────────────────────────────────────────────────────────

    @app.get("/api/agents/{agent_id}/trades")
    async def get_trades(agent_id: str, limit: int = 50):
        return await db.get_trades(agent_id, limit=limit)

    class OrderRequest(BaseModel):
        symbol: str
        side: str
        qty: int
        price: Optional[float] = None
        stop_loss: Optional[float] = None
        take_profit: Optional[float] = None
        reason: str = ""
        strategy: str = ""
        tags: list[str] = []
        confidence: Optional[float] = None

    @app.post("/api/agents/{agent_id}/orders")
    async def place_order(agent_id: str, req: OrderRequest):
        msg = await services.place_order(
            agent_id,
            req.symbol, req.side, req.qty, req.price,
            req.stop_loss, req.take_profit,
            req.reason, req.strategy, req.tags, req.confidence,
        )
        return {"message": msg}

    class UpdateOrderRequest(BaseModel):
        symbol: str
        stop_loss: Optional[float] = None
        take_profit: Optional[float] = None

    @app.patch("/api/agents/{agent_id}/orders")
    async def update_order(agent_id: str, req: UpdateOrderRequest):
        msg = await services.modify_orders(agent_id, req.symbol, req.stop_loss, req.take_profit)
        return {"message": msg}

    # ── Journals ──────────────────────────────────────────────────────────────

    @app.get("/api/agents/{agent_id}/journals")
    async def list_journals(agent_id: str, limit: int = 10):
        return await db.list_journals(agent_id, limit=limit)

    @app.get("/api/agents/{agent_id}/journals/{date_str}")
    async def get_journal(agent_id: str, date_str: str):
        data = await db.get_journal(agent_id, date_str)
        return {"date": date_str, "content": data}

    # ── Market ────────────────────────────────────────────────────────────────

    @app.get("/api/market/snapshot")
    async def get_market_snapshot():
        return await db.get_latest_market_snapshot()

    @app.get("/api/market/quote/{symbol}")
    async def get_quote(symbol: str):
        from backend.core.market_data import get_quote as _get_quote
        try:
            q = _get_quote(symbol)
            return q.model_dump()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/market/technical/{symbol}")
    async def get_technical(symbol: str):
        from backend.core.market_service import build_stock_analysis
        try:
            return build_stock_analysis(symbol)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/market/news")
    async def get_news(category: str = "tw_stock", limit: int = 10):
        from backend.core.market_service import get_market_news_raw
        return get_market_news_raw(category, limit=limit)

    # ── Agents ────────────────────────────────────────────────────────────────

    @app.get("/api/agents/{agent_id}")
    async def get_agent(agent_id: str):
        agent = await db.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent

    class CreateAgentRequest(BaseModel):
        user_id: str
        name: str
        config: dict = {}

    @app.post("/api/agents")
    async def create_agent(req: CreateAgentRequest):
        return await db.create_agent(req.user_id, req.name, req.config)

    # ── Heartbeat (manual trigger) ────────────────────────────────────────────

    @app.post("/api/agents/{agent_id}/heartbeat/{phase}")
    async def trigger_heartbeat(agent_id: str, phase: str):
        if phase not in ("pre_market", "intraday", "post_market"):
            raise HTTPException(status_code=400, detail="Invalid phase")
        from backend.tasks import _heartbeat
        await _heartbeat(agent_id, phase)
        return {"status": "ok", "phase": phase}

    return app

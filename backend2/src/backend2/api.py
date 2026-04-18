from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend2 import db, workspace
from backend2.market import build_analysis, build_overview, get_news, get_quote
from backend2.models import (
    JournalEntry,
    LessonsDocument,
    OrderRequest,
    OrderUpdateRequest,
    WatchlistConfig,
    WatchlistItem,
)
from backend2.runtime import (
    get_market_profile_for_runtime,
    get_runtime_config,
    get_trading_state,
    get_workspace_status,
    heartbeat,
    place_order,
    update_orders,
)
from backend2.screener import run_screener
from backend2.watchlist import load_evaluated_watchlist


def create_app() -> FastAPI:
    app = FastAPI(title="Backend2")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        await db.get_connection()
        return {"status": "ok"}

    @app.get("/workspace")
    async def get_workspace():
        return workspace.load_runtime_config()

    @app.get("/state")
    async def get_state():
        return await get_trading_state()

    @app.get("/account")
    async def get_account_status():
        return await get_workspace_status()

    @app.get("/trades")
    async def get_trades(limit: int = 50):
        return await db.list_trades(workspace.load_runtime_config().id, limit=limit)

    @app.get("/overview")
    async def get_overview():
        try:
            config = get_runtime_config()
            profile = get_market_profile_for_runtime(config)
            return build_overview(config, profile)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/news")
    async def get_workspace_news():
        try:
            return get_news(get_runtime_config())
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/quote/{symbol:path}")
    async def get_workspace_quote(symbol: str):
        try:
            return get_quote(symbol, get_market_profile_for_runtime())
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/analysis/{symbol:path}")
    async def get_workspace_analysis(symbol: str):
        try:
            config = get_runtime_config()
            profile = get_market_profile_for_runtime(config)
            return build_analysis(symbol, config, profile)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/chart/{symbol:path}")
    async def get_workspace_chart(symbol: str):
        try:
            config = get_runtime_config()
            profile = get_market_profile_for_runtime(config)
            
            from backend2.market import analyze_symbol
            import pandas as pd
            
            snapshot = analyze_symbol(symbol, config, profile)
            
            df = snapshot.dataframe
            indicators = {}
            if "SMA_20" in df.columns:
                indicators["sma20"] = [None if pd.isna(v) else float(v) for v in df["SMA_20"]]
            elif "sma20" in df.columns:
                indicators["sma20"] = [None if pd.isna(v) else float(v) for v in df["sma20"]]
            
            return {
                "bars": [b.model_dump() for b in snapshot.bars],
                "indicators": indicators,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/screener")
    async def get_workspace_screener(
        strategy: str = "momentum",
        enrich: bool = True,
        limit: int = 30,
    ):
        try:
            config = get_runtime_config()
            profile = get_market_profile_for_runtime(config)
            return run_screener(config, profile, strategy=strategy, enrich=enrich, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/orders")
    async def submit_order(request: OrderRequest):
        return {"message": await place_order(request)}

    @app.patch("/orders")
    async def patch_orders(request: OrderUpdateRequest):
        return {"message": await update_orders(request)}

    @app.post("/heartbeat")
    async def run_heartbeat():
        return await heartbeat()

    @app.get("/equity-history")
    async def get_equity_history(days: int = 90):
        return await db.list_account_snapshots(workspace.load_runtime_config().id, days=days)

    @app.get("/snapshots/latest")
    async def latest_snapshot():
        return await db.get_latest_market_snapshot(workspace.load_runtime_config().id)

    @app.get("/workspace/watchlist")
    async def get_workspace_watchlist(evaluate: bool = True):
        try:
            config = get_runtime_config()
            if not evaluate:
                return workspace.load_watchlist(config)
            profile = get_market_profile_for_runtime(config)
            return load_evaluated_watchlist(config, profile)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/workspace/watchlist")
    async def replace_workspace_watchlist(payload: WatchlistConfig):
        try:
            return workspace.save_watchlist(get_runtime_config(), payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/workspace/watchlist/items")
    async def upsert_workspace_watchlist_item(payload: WatchlistItem):
        try:
            return workspace.upsert_watchlist_item(get_runtime_config(), payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/workspace/journals")
    async def get_workspace_journals(limit: int = 5):
        try:
            return workspace.list_journals(get_runtime_config(), limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/workspace/journals/{date_str}")
    async def get_workspace_journal(date_str: str):
        try:
            return workspace.load_journal(get_runtime_config(), date_str)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/workspace/journals/{date_str}/entries")
    async def append_workspace_journal_entry(date_str: str, payload: JournalEntry):
        try:
            return workspace.append_journal_entry(get_runtime_config(), date_str, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/workspace/lessons")
    async def get_workspace_lessons():
        try:
            return workspace.load_lessons(get_runtime_config())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/workspace/lessons")
    async def update_workspace_lessons(payload: LessonsDocument):
        try:
            return workspace.save_lessons(get_runtime_config(), payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/workspace/research-cards/{date_str}")
    async def save_workspace_research_card(date_str: str, payload: dict):
        try:
            return workspace.save_research_card(get_runtime_config(), date_str, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app

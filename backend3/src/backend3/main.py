from __future__ import annotations

import logging

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from backend3.db import close_connection, get_connection
from backend3.routes import auth, docs, events, journals, operations, snapshots, views, watchlist

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def build_app() -> FastAPI:
    app = FastAPI(title="backend3", version="0.1.0", docs_url="/api-docs", redoc_url="/api-redoc")

    @app.on_event("startup")
    async def startup() -> None:
        await get_connection()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await close_connection()

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    app.include_router(auth.router, tags=["auth"])
    app.include_router(events.router, tags=["events"])
    app.include_router(journals.router, tags=["journals"])
    app.include_router(docs.router, tags=["docs"])
    app.include_router(watchlist.router, tags=["watchlist"])
    app.include_router(operations.router, tags=["operations"])
    app.include_router(snapshots.router, tags=["snapshots"])
    app.include_router(views.router, tags=["views"])
    return app


app = build_app()


def main() -> None:
    uvicorn.run("backend3.main:app", host="0.0.0.0", port=8100, reload=False)

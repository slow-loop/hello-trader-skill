from __future__ import annotations

import logging
import os
from dotenv import load_dotenv

import uvicorn

load_dotenv()

from backend2.api import create_app
from backend2.db import close_connection, get_connection
from backend2.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def build_app():
    app = create_app()
    # scheduler = setup_scheduler()

    @app.on_event("startup")
    async def startup() -> None:
        await get_connection()
        # if scheduler.get_jobs():
        #     scheduler.start()
        #     logging.getLogger(__name__).info("scheduler started")
        pass

    @app.on_event("shutdown")
    async def shutdown() -> None:
        # if scheduler.running:
        #     scheduler.shutdown(wait=False)
        pass
        await close_connection()

    return app


app = build_app()


def main() -> None:
    uvicorn.run("backend2.main:app", host="0.0.0.0", port=8000, reload=False)

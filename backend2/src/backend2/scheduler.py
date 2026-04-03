from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend2.runtime import heartbeat
from backend2.workspace import load_runtime_config

logger = logging.getLogger(__name__)


def setup_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    config = load_runtime_config()
    if not config.schedule.enabled:
        return scheduler

    interval_minutes = config.schedule.snapshot_interval_minutes

    async def _tick() -> None:
        try:
            await heartbeat()
        except Exception as exc:
            logger.warning("heartbeat failed: %s", exc)

    scheduler.add_job(_tick, "interval", minutes=interval_minutes, id="workspace-heartbeat", replace_existing=True)
    return scheduler

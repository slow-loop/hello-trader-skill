"""
tasks.py — APScheduler heartbeat jobs (Taiwan market sessions).
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend import database as db
from backend import services

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Taipei")


async def _run_all_agents(phase: str) -> None:
    """Run heartbeat for all active agents."""
    agent_ids = await db.list_all_active_agents()
    for agent_id in agent_ids:
        try:
            await _heartbeat(agent_id, phase)
        except Exception as e:
            logger.error("Heartbeat failed for agent %s phase %s: %s", agent_id, phase, e)


async def _heartbeat(agent_id: str, phase: str) -> None:
    logger.info("[heartbeat] agent=%s phase=%s", agent_id, phase)

    # 1. Capture market snapshot (shared across agents)
    try:
        await services.capture_market_snapshot(phase)
    except Exception as e:
        logger.warning("Market snapshot failed: %s", e)

    # 2. Check pending orders + update prices
    try:
        await services.get_portfolio(agent_id)  # triggers check_pending_orders internally
    except Exception as e:
        logger.warning("Portfolio check failed for %s: %s", agent_id, e)

    # 3. Record daily equity snapshot (post_market only)
    if phase == "post_market":
        try:
            await services.record_snapshot(agent_id)
        except Exception as e:
            logger.warning("Equity snapshot failed for %s: %s", agent_id, e)


def setup_scheduler() -> AsyncIOScheduler:
    # Taiwan market sessions
    scheduler.add_job(
        _run_all_agents, "cron",
        hour=8, minute=30,
        args=["pre_market"],
        id="pre_market",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_all_agents, "cron",
        hour=9, minute=30,
        args=["intraday"],
        id="intraday",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_all_agents, "cron",
        hour=13, minute=35,
        args=["post_market"],
        id="post_market",
        replace_existing=True,
    )
    return scheduler

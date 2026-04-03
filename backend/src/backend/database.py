"""
database.py — Backend selector.

Set DB_BACKEND env var to choose the storage backend:
  DB_BACKEND=sqlite    (default) — local SQLite via aiosqlite
  DB_BACKEND=supabase             — Supabase (cloud)

All exported functions are async regardless of backend.
"""

from __future__ import annotations

import asyncio
import functools
import os

_BACKEND = os.getenv("DB_BACKEND", "sqlite")

if _BACKEND == "supabase":
    # Wrap the sync Supabase functions so callers can always use await.
    import backend.database_supabase as _supa

    def _async(fn):
        @functools.wraps(fn)
        async def _wrapper(*args, **kwargs):
            return await asyncio.to_thread(fn, *args, **kwargs)
        return _wrapper

    get_agent             = _async(_supa.get_agent)
    list_agents           = _async(_supa.list_agents)
    list_all_active_agents = _async(_supa.list_all_active_agents)
    create_agent          = _async(_supa.create_agent)
    update_agent_config   = _async(_supa.update_agent_config)

    get_account_data      = _async(_supa.get_account_data)
    save_account_data     = _async(_supa.save_account_data)

    insert_trade          = _async(_supa.insert_trade)
    get_trades            = _async(_supa.get_trades)
    get_trades_since      = _async(_supa.get_trades_since)

    upsert_equity_snapshot = _async(_supa.upsert_equity_snapshot)
    get_equity_snapshots   = _async(_supa.get_equity_snapshots)

    get_journal           = _async(_supa.get_journal)
    upsert_journal        = _async(_supa.upsert_journal)
    list_journals         = _async(_supa.list_journals)

    upsert_market_snapshot   = _async(_supa.upsert_market_snapshot)
    get_market_snapshot      = _async(_supa.get_market_snapshot)
    get_latest_market_snapshot = _async(_supa.get_latest_market_snapshot)

else:
    from backend.database_sqlite import (
        get_agent,
        list_agents,
        list_all_active_agents,
        create_agent,
        update_agent_config,
        get_account_data,
        save_account_data,
        insert_trade,
        get_trades,
        get_trades_since,
        upsert_equity_snapshot,
        get_equity_snapshots,
        get_journal,
        upsert_journal,
        list_journals,
        upsert_market_snapshot,
        get_market_snapshot,
        get_latest_market_snapshot,
    )

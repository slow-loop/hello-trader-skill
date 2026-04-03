"""
database_supabase.py — Supabase client + CRUD for all tables.

All functions return Pydantic models (same interface as database_sqlite.py).

Tables:
  agents            — agent config per user
  accounts          — ledger state per agent (JSONB)
  trades            — trade history (agent_id + executed_at indexed)
  equity_snapshots  — daily snapshots (agent_id + date PK)
  journals          — daily journals (agent_id + date PK)
  market_snapshots  — shared market state (date + session unique)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from supabase import create_client, Client
from backend.config import SUPABASE_URL, SUPABASE_KEY
from backend.models import (
    AgentRow,
    EquitySnapshot,
    Ledger,
    MarketOverview,
    TradeRecord,
)

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ── Agents ────────────────────────────────────────────────────────────────────

def get_agent(agent_id: str) -> Optional[AgentRow]:
    res = get_client().table("agents").select("*").eq("id", agent_id).single().execute()
    return AgentRow.model_validate(res.data) if res.data else None


def list_agents(user_id: str) -> List[AgentRow]:
    res = get_client().table("agents").select("*").eq("user_id", user_id).eq("is_active", True).execute()
    return [AgentRow.model_validate(r) for r in (res.data or [])]


def list_all_active_agents() -> List[str]:
    """Return IDs of all active agents (used by scheduler)."""
    res = get_client().table("agents").select("id").eq("is_active", True).execute()
    return [row["id"] for row in (res.data or [])]


def create_agent(user_id: str, name: str, config: Dict[str, Any]) -> AgentRow:
    res = get_client().table("agents").insert({
        "user_id": user_id,
        "name": name,
        "config": config,
        "is_active": True,
    }).execute()
    return AgentRow.model_validate(res.data[0])


def update_agent_config(agent_id: str, config: Dict[str, Any]) -> None:
    get_client().table("agents").update({"config": config}).eq("id", agent_id).execute()


# ── Accounts (ledger state) ───────────────────────────────────────────────────

def get_account_data(agent_id: str) -> Ledger:
    from backend.core.trading_engine import default_ledger
    res = get_client().table("accounts").select("data").eq("agent_id", agent_id).execute()
    if res.data:
        return Ledger.model_validate(res.data[0]["data"])
    return default_ledger()


def save_account_data(agent_id: str, ledger: Ledger) -> None:
    get_client().table("accounts").upsert({
        "agent_id": agent_id,
        "data": ledger.model_dump(),
    }).execute()


# ── Trades ────────────────────────────────────────────────────────────────────

def insert_trade(agent_id: str, trade: TradeRecord) -> None:
    get_client().table("trades").insert({
        "agent_id": agent_id,
        "executed_at": trade.executed_at,
        "data": trade.model_dump(),
    }).execute()


def get_trades(agent_id: str, limit: int = 50) -> List[TradeRecord]:
    res = (
        get_client()
        .table("trades")
        .select("data")
        .eq("agent_id", agent_id)
        .order("executed_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [TradeRecord.model_validate(row["data"]) for row in (res.data or [])]


def get_trades_since(agent_id: str, since: str) -> List[TradeRecord]:
    res = (
        get_client()
        .table("trades")
        .select("data")
        .eq("agent_id", agent_id)
        .gte("executed_at", since)
        .order("executed_at")
        .execute()
    )
    return [TradeRecord.model_validate(row["data"]) for row in (res.data or [])]


# ── Equity Snapshots ──────────────────────────────────────────────────────────

def upsert_equity_snapshot(agent_id: str, snapshot: EquitySnapshot) -> None:
    get_client().table("equity_snapshots").upsert({
        "agent_id": agent_id,
        "date": snapshot.date,
        "data": snapshot.model_dump(),
    }).execute()


def get_equity_snapshots(agent_id: str, days: int = 90) -> List[EquitySnapshot]:
    res = (
        get_client()
        .table("equity_snapshots")
        .select("date, data")
        .eq("agent_id", agent_id)
        .order("date", desc=True)
        .limit(days)
        .execute()
    )
    return [EquitySnapshot.model_validate(row["data"]) for row in reversed(res.data or [])]


# ── Journals (open-ended content — stored as raw JSON) ────────────────────────

def get_journal(agent_id: str, date_str: str) -> Optional[Dict[str, Any]]:
    res = (
        get_client()
        .table("journals")
        .select("data")
        .eq("agent_id", agent_id)
        .eq("date", date_str)
        .execute()
    )
    return res.data[0]["data"] if res.data else None


def upsert_journal(agent_id: str, date_str: str, content: Dict[str, Any]) -> None:
    get_client().table("journals").upsert({
        "agent_id": agent_id,
        "date": date_str,
        "data": content,
    }).execute()


def list_journals(agent_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    res = (
        get_client()
        .table("journals")
        .select("date, data")
        .eq("agent_id", agent_id)
        .order("date", desc=True)
        .limit(limit)
        .execute()
    )
    return [{"date": r["date"], **r["data"]} for r in (res.data or [])]


# ── Market Snapshots ──────────────────────────────────────────────────────────

def upsert_market_snapshot(date_str: str, session: str, data: MarketOverview) -> None:
    get_client().table("market_snapshots").upsert({
        "date": date_str,
        "session": session,
        "data": data.model_dump(),
    }).execute()


def get_market_snapshot(date_str: str, session: str) -> Optional[MarketOverview]:
    res = (
        get_client()
        .table("market_snapshots")
        .select("data")
        .eq("date", date_str)
        .eq("session", session)
        .execute()
    )
    return MarketOverview.model_validate(res.data[0]["data"]) if res.data else None


def get_latest_market_snapshot() -> Optional[MarketOverview]:
    res = (
        get_client()
        .table("market_snapshots")
        .select("date, session, data")
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    return MarketOverview.model_validate(res.data[0]["data"]) if res.data else None

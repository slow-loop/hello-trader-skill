from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

TMP_DB = Path(tempfile.mkdtemp()) / "backend3_test.db"
os.environ["BACKEND3_DB"] = str(TMP_DB)

from httpx import ASGITransport, AsyncClient

from backend3 import db as db_mod
from backend3.main import app

db_mod.DB_PATH = TMP_DB


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _register(client, name="agentA") -> tuple[int, dict]:
    r = await client.post("/auth/register", json={"name": name})
    assert r.status_code == 200, r.text
    data = r.json()
    headers = {"Authorization": f"Bearer {data['token']}"}
    return data["agent_id"], headers


@pytest.mark.asyncio
async def test_full_flow(client):
    agent_id, headers = await _register(client)
    me = (await client.get("/me", headers=headers)).json()
    assert me["agent_id"] == agent_id

    assert (await client.get("/me")).status_code == 401

    # Journals
    r = await client.post(
        "/journals", headers=headers,
        json={"date": "2026-04-19", "entry_type": "daily", "body": "hello"},
    )
    assert r.status_code == 200
    js = (await client.get("/journals", headers=headers)).json()
    assert len(js) == 1

    # Docs with path-based versioning
    r1 = await client.post(
        "/docs", headers=headers,
        json={"path": "lessons.md", "body": "v1"},
    )
    assert r1.json()["version"] == 1
    r2 = await client.post(
        "/docs", headers=headers,
        json={"path": "lessons.md", "body": "v2"},
    )
    assert r2.json()["version"] == 2
    latest = (await client.get("/docs/latest", headers=headers, params={"path": "lessons.md"})).json()
    assert latest["body"] == "v2"

    # Doc prefix listing shows latest only
    await client.post("/docs", headers=headers, json={"path": "research/2026-04-19-tw-2330.md", "body": "# tsmc"})
    await client.post("/docs", headers=headers, json={"path": "research/2026-04-19-market-scan-0930.yaml", "body": "top:\n  - 2330"})
    rdocs = (await client.get("/docs", headers=headers, params={"prefix": "research/"})).json()
    assert len(rdocs) == 2
    all_docs = (await client.get("/docs", headers=headers)).json()
    assert len(all_docs) == 3  # lessons.md + 2 research

    # Watchlist
    await client.put(
        "/watchlist/2330.TW", headers=headers,
        json={"thesis": "AI capex", "status": "active", "metadata": {"trigger_price": 950}},
    )
    wl = (await client.get("/watchlist", headers=headers)).json()
    assert len(wl) == 1 and wl[0]["symbol"] == "2330.TW"

    # Operation + trade
    op = (await client.post(
        "/operations", headers=headers,
        json={"symbol": "2330.TW", "side": "buy", "qty": 100, "price": 950, "reason": "breakout"},
    )).json()
    assert op["status"] == "proposed"
    tr = await client.post(
        "/trades", headers=headers,
        json={"operation_id": op["id"], "fill_price": 951.0, "fees": 50},
    )
    assert tr.status_code == 200, tr.text

    # Cannot patch executed op
    bad = await client.patch(
        f"/operations/{op['id']}", headers=headers, json={"status": "canceled"}
    )
    assert bad.status_code == 409

    # Positions
    positions = (await client.get("/positions", headers=headers)).json()
    assert positions[0]["qty"] == 100
    assert abs(positions[0]["avg_cost"] - 951.0) < 1e-6

    # Sell half
    op2 = (await client.post(
        "/operations", headers=headers,
        json={"symbol": "2330.TW", "side": "sell", "qty": 50, "price": 980, "reason": "trim"},
    )).json()
    await client.post("/trades", headers=headers, json={"operation_id": op2["id"], "fill_price": 980, "pnl": 1450})
    positions = (await client.get("/positions", headers=headers)).json()
    assert positions[0]["qty"] == 50

    # Snapshot
    snap = await client.post(
        "/snapshots", headers=headers,
        json={"kind": "screener", "source": "momentum", "summary": {"count": 5}, "payload": "local://data/x.json"},
    )
    assert snap.status_code == 200

    # Events
    events = (await client.get("/events", headers=headers)).json()
    types = {e["type"] for e in events}
    expected = {
        "agent.created", "journal.appended", "doc.saved",
        "watchlist.upserted", "operation.proposed", "trade.recorded",
        "operation.executed", "snapshot.saved",
    }
    assert expected <= types

    # Account view
    acct = (await client.get("/account", headers=headers)).json()
    assert acct["trade_count"] == 2

    # Isolation
    _, headers_b = await _register(client, name="agentB")
    assert (await client.get("/watchlist", headers=headers_b)).json() == []
    assert (await client.get("/docs", headers=headers_b)).json() == []


@pytest.mark.asyncio
async def test_reject_operation(client):
    _, headers = await _register(client, name="agentC")
    op = (await client.post(
        "/operations", headers=headers,
        json={"symbol": "2454.TW", "side": "buy", "qty": 10, "price": 100, "reason": "test"},
    )).json()
    r = await client.patch(
        f"/operations/{op['id']}", headers=headers,
        json={"status": "rejected", "rejected_reason": "risk too high"},
    )
    assert r.status_code == 200 and r.json()["status"] == "rejected"

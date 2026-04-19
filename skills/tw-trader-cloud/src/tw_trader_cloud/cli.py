from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import typer
import yaml

from tw_trader_cloud.client import ACCOUNT_DIR, CONFIG_PATH, Client, load_config, save_config

app = typer.Typer(add_completion=False, no_args_is_help=True, help="tw-trader-cloud CLI (backend3 client)")


def _echo(obj: Any) -> None:
    typer.echo(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _parse_metadata(raw: str | None) -> dict:
    if not raw:
        return {}
    return json.loads(raw)


def _cache_write(rel_path: str, text: str) -> Path:
    p = ACCOUNT_DIR / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# ─── setup ───────────────────────────────────────────────────────────────────

@app.command()
def init(
    name: str = typer.Option(..., help="Agent name (globally unique on backend)"),
    backend_url: str = typer.Option("http://localhost:8100", help="Backend3 URL"),
) -> None:
    """One-time setup: register agent and save token to agent.yaml."""
    if CONFIG_PATH.exists():
        cfg = load_config()
        if cfg.get("token"):
            typer.echo(f"Already configured as '{cfg.get('agent_name')}'; token present.")
            raise typer.Exit(0)
    r = httpx.post(f"{backend_url}/auth/register", json={"name": name}, timeout=10.0)
    if r.status_code >= 400:
        typer.echo(f"Register failed: {r.status_code} {r.text}")
        raise typer.Exit(1)
    data = r.json()
    save_config({"backend_url": backend_url, "agent_name": data["name"], "token": data["token"]})
    typer.echo(f"Registered agent_id={data['agent_id']} name={data['name']}")


@app.command()
def me() -> None:
    _echo(Client.from_config().get("/me"))


# ─── watchlist ───────────────────────────────────────────────────────────────

@app.command()
def watchlist() -> None:
    """GET /watchlist and overwrite local cache at data/account/watchlist.yaml."""
    items = Client.from_config().get("/watchlist")
    text = yaml.safe_dump(items, allow_unicode=True, sort_keys=False)
    path = _cache_write("watchlist.yaml", text)
    typer.echo(f"wrote {path} ({len(items)} items)")
    _echo(items)


@app.command("watchlist-update")
def watchlist_update(
    symbol: str,
    thesis: str = typer.Option(None),
    status: str = typer.Option("active"),
    trigger_price: float = typer.Option(None, "--trigger-price"),
    stop: float = typer.Option(None, "--stop"),
    target: float = typer.Option(None, "--target"),
    metadata: str = typer.Option(None, help="Extra JSON metadata to merge"),
) -> None:
    meta = _parse_metadata(metadata)
    if trigger_price is not None:
        meta["trigger_price"] = trigger_price
    if stop is not None:
        meta["stop"] = stop
    if target is not None:
        meta["target"] = target
    _echo(Client.from_config().put(
        f"/watchlist/{symbol}",
        {"thesis": thesis, "status": status, "metadata": meta},
    ))


@app.command("watchlist-remove")
def watchlist_remove(symbol: str) -> None:
    _echo(Client.from_config().delete(f"/watchlist/{symbol}"))


# ─── journal ─────────────────────────────────────────────────────────────────

@app.command()
def journal(
    from_date: str = typer.Option(None, "--from-date"),
    to_date: str = typer.Option(None, "--to-date"),
    entry_type: str = typer.Option(None, "--entry-type"),
) -> None:
    """GET /journals and write cache under data/account/journals/{date}.yaml (grouped by date)."""
    entries = Client.from_config().get(
        "/journals", from_date=from_date, to_date=to_date, entry_type=entry_type
    )
    by_date: dict[str, list] = {}
    for e in entries:
        by_date.setdefault(e["date"], []).append(e)
    for date, items in by_date.items():
        text = yaml.safe_dump(items, allow_unicode=True, sort_keys=False)
        _cache_write(f"journals/{date}.yaml", text)
    typer.echo(f"wrote {len(by_date)} files, {len(entries)} entries")
    _echo(entries)


@app.command("journal-add")
def journal_add(
    date: str = typer.Option(..., help="YYYY-MM-DD"),
    entry_type: str = typer.Option(..., "--entry-type", help="daily|research|trading|reflection"),
    body: str = typer.Option("", help="Short markdown summary"),
    metadata: str = typer.Option(None, help="JSON metadata"),
) -> None:
    meta = _parse_metadata(metadata)
    _echo(Client.from_config().post(
        "/journals",
        {"date": date, "entry_type": entry_type, "body": body, "metadata": meta},
    ))


# ─── operations / trades ─────────────────────────────────────────────────────

@app.command()
def buy(
    symbol: str,
    qty: float = typer.Option(...),
    price: float = typer.Option(...),
    reason: str = typer.Option(...),
    stop: float = typer.Option(None),
    target: float = typer.Option(None),
    metadata: str = typer.Option(None),
) -> None:
    """Propose + fill in one step (paper mode)."""
    meta = _parse_metadata(metadata)
    if stop is not None:
        meta["stop"] = stop
    if target is not None:
        meta["target"] = target
    c = Client.from_config()
    op = c.post("/operations", {
        "symbol": symbol, "side": "buy", "qty": qty, "price": price,
        "reason": reason, "metadata": meta,
    })
    trade = c.post("/trades", {"operation_id": op["id"], "fill_price": price})
    _echo({"operation": op, "trade": trade})


@app.command()
def sell(
    symbol: str,
    qty: float = typer.Option(...),
    price: float = typer.Option(...),
    reason: str = typer.Option(...),
    pnl: float = typer.Option(None),
    metadata: str = typer.Option(None),
) -> None:
    meta = _parse_metadata(metadata)
    c = Client.from_config()
    op = c.post("/operations", {
        "symbol": symbol, "side": "sell", "qty": qty, "price": price,
        "reason": reason, "metadata": meta,
    })
    trade = c.post("/trades", {"operation_id": op["id"], "fill_price": price, "pnl": pnl})
    _echo({"operation": op, "trade": trade})


@app.command()
def propose(
    symbol: str = typer.Option(...),
    side: str = typer.Option(...),
    qty: float = typer.Option(...),
    price: float = typer.Option(...),
    reason: str = typer.Option(...),
    metadata: str = typer.Option(None),
) -> None:
    """Propose only — no fill. Use `fill` later."""
    _echo(Client.from_config().post("/operations", {
        "symbol": symbol, "side": side, "qty": qty, "price": price,
        "reason": reason, "metadata": _parse_metadata(metadata),
    }))


@app.command()
def fill(
    operation_id: int,
    fill_price: float = typer.Option(..., "--fill-price"),
    qty: float = typer.Option(None),
    fees: float = typer.Option(0.0),
    pnl: float = typer.Option(None),
) -> None:
    _echo(Client.from_config().post("/trades", {
        "operation_id": operation_id, "fill_price": fill_price,
        "qty": qty, "fees": fees, "pnl": pnl,
    }))


@app.command()
def reject(operation_id: int, reason: str = typer.Option(...)) -> None:
    _echo(Client.from_config().patch(
        f"/operations/{operation_id}",
        {"status": "rejected", "rejected_reason": reason},
    ))


@app.command()
def cancel(operation_id: int, reason: str = typer.Option(...)) -> None:
    _echo(Client.from_config().patch(
        f"/operations/{operation_id}",
        {"status": "canceled", "rejected_reason": reason},
    ))


@app.command()
def account() -> None:
    c = Client.from_config()
    _echo({
        "account": c.get("/account"),
        "positions": c.get("/positions"),
        "proposed_operations": c.get("/operations", status="proposed"),
    })


@app.command()
def events(
    from_ts: str = typer.Option(None, "--from-ts"),
    types: str = typer.Option(None),
    limit: int = typer.Option(100),
) -> None:
    _echo(Client.from_config().get("/events", from_ts=from_ts, types=types, limit=limit))


# ─── docs ────────────────────────────────────────────────────────────────────

def _path_to_backend(local_path: Path) -> str:
    """Translate a local path under data/account/... into a backend doc path."""
    abs_local = local_path.resolve()
    abs_account = ACCOUNT_DIR.resolve()
    try:
        rel = abs_local.relative_to(abs_account)
    except ValueError:
        raise typer.BadParameter(
            f"{local_path} is not under {ACCOUNT_DIR}"
        )
    return str(rel).replace("\\", "/")


@app.command("docs-add")
def docs_add(file: Path) -> None:
    """Push a local file under data/account/ to backend as a doc.

    YAML files (.yaml/.yml) are parse-validated before upload.
    """
    if not file.exists():
        raise typer.BadParameter(f"{file} does not exist")
    text = file.read_text(encoding="utf-8")
    if file.suffix in (".yaml", ".yml"):
        try:
            yaml.safe_load(text)
        except yaml.YAMLError as e:
            typer.echo(f"YAML parse error in {file}: {e}")
            raise typer.Exit(1)
    doc_path = _path_to_backend(file)
    _echo(Client.from_config().post("/docs", {"path": doc_path, "body": text}))


def _fetch_docs_to_cache(prefix: str) -> list[dict]:
    docs = Client.from_config().get("/docs", prefix=prefix)
    for d in docs:
        _cache_write(d["path"], d["body"])
    return docs


@app.command()
def research(from_date: str = typer.Option(None, "--from-date")) -> None:
    """Fetch research/* docs from backend into local cache."""
    prefix = f"research/{from_date}" if from_date else "research/"
    docs = _fetch_docs_to_cache(prefix)
    typer.echo(f"wrote {len(docs)} files")
    _echo([{"path": d["path"], "version": d["version"]} for d in docs])


@app.command()
def lessons() -> None:
    """Fetch lessons.md from backend into local cache."""
    try:
        doc = Client.from_config().get("/docs/latest", path="lessons.md")
        _cache_write("lessons.md", doc["body"])
        typer.echo(f"wrote lessons.md (v{doc['version']})")
    except RuntimeError as e:
        if "404" in str(e):
            typer.echo("no lessons.md on backend yet")
            return
        raise


if __name__ == "__main__":
    app()

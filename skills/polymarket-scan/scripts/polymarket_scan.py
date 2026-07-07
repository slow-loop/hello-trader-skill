#!/usr/bin/env python3
"""Polymarket scanner — one script, two subcommands, for the "answer is
obvious but the price hasn't caught up" hunt.

Self-contained: resolves gamma-api.polymarket.com over DoH (direct to
Cloudflare 1.1.1.1) so it works even when local/ISP DNS poisons it. No system
DNS change or VPN needed. Stdlib only.

Subcommands:
  moneyline   Sports, single-match win/lose(/draw) markets, across ALL sports
              at once — no tag list needed.
              GET /markets?sports_market_types=moneyline&order=createdAt...
              paginated (offset) until createdAt falls before --since.
              `sports_market_types` is an undocumented field that only works
              on /markets (silently ignored on /events). It classifies "is
              this a single match's win/lose outcome" — not "exactly 2
              outcomes", and not tournament-winner markets (those span many
              matches, not one). Soccer's win/win/draw triple (3 separate
              Yes/No markets per match) is merged back into one row.
              Doesn't cover boxing/mma (no sportsMarketType field, and the
              category is sparse/irregular enough it's not worth a separate
              path — see `tagged` for elections instead).

  tagged      /events + tag_slug engine. Used for elections/politics — not
              sports at all, no moneyline classification applies. Several
              presets (see PRESETS below).

Examples:
  python3 polymarket_scan.py moneyline --since 2026-07-04
  python3 polymarket_scan.py tagged --mode fresh --tags elections,world-elections
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import ssl
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GAMMA_HOST = "gamma-api.polymarket.com"
GAMMA_API = f"https://{GAMMA_HOST}"
DOH_SERVERS = (("1.1.1.1", "/dns-query"), ("8.8.8.8", "/resolve"))  # Cloudflare, then Google DoH — try in order; different JSON API path per provider
PAGE = 100  # server hard-caps /markets and /events at 100 regardless of requested limit


# --- networking (DoH override so it works on poisoned DNS) ------------------

def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if not ctx.get_ca_certs():
        for path in ("/etc/ssl/cert.pem", "/private/etc/ssl/cert.pem"):
            if os.path.exists(path):
                ctx.load_verify_locations(path)
                break
    return ctx


SSL_CTX = _ssl_context()


def install_doh_override() -> None:
    params = urlencode({"name": GAMMA_HOST, "type": "A"})
    last_exc = None
    ips: list[str] = []
    for doh_ip, doh_path in DOH_SERVERS:
        req = Request(f"https://{doh_ip}{doh_path}?{params}",
                      headers={"accept": "application/dns-json"})
        try:
            with urlopen(req, timeout=12, context=SSL_CTX) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            ips = [a["data"] for a in payload.get("Answer", []) if a.get("type") == 1]
            if ips:
                break
        except Exception as exc:  # try the next DoH server
            last_exc = exc
    if not ips:
        raise RuntimeError(f"DoH could not resolve {GAMMA_HOST} via {DOH_SERVERS}") from last_exc
    ip = ips[0]
    real = socket.getaddrinfo

    def patched(host, *args, **kwargs):
        return real(ip if host == GAMMA_HOST else host, *args, **kwargs)

    socket.getaddrinfo = patched  # type: ignore[assignment]


def _get(path: str, params: dict) -> list[dict]:
    req = Request(f"{GAMMA_API}{path}?{urlencode(params)}",
                  headers={"User-Agent": "polymarket-scan/1.0", "Accept": "application/json"})
    with urlopen(req, timeout=30, context=SSL_CTX) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data if isinstance(data, list) else []


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# =============================================================================
# moneyline subcommand — sports, all leagues at once, newest-first
# =============================================================================

DRAW_RE = re.compile(r"^Will (.+?) vs\.? (.+?) end in a draw\?$")
WIN_RE = re.compile(r"^Will (.+?) win on ")


def fetch_moneyline_since(since_date: str, max_pages: int) -> list[dict]:
    """Page back through createdAt-descending /markets results until we cross since_date."""
    markets: list[dict] = []
    offset = 0
    for _ in range(max_pages):
        page = _get("/markets", {
            "sports_market_types": "moneyline", "active": "true", "closed": "false",
            "order": "createdAt", "ascending": "false", "limit": str(PAGE), "offset": str(offset),
        })
        if not page:
            break
        stop = False
        for m in page:
            created = m.get("createdAt") or ""
            if created[:10] < since_date:
                stop = True
                break
            markets.append(m)
        if stop or len(page) < PAGE:
            break
        offset += PAGE
    return markets


def _outcomes(m: dict) -> list[str]:
    try:
        return json.loads(m.get("outcomes") or "[]")
    except (json.JSONDecodeError, TypeError):
        return []


def _prices(m: dict) -> list[float]:
    try:
        return [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def merge_moneyline_rows(markets: list[dict]) -> list[dict]:
    """Collapse soccer's win/win/draw triple into one row per match."""
    soccer: dict[frozenset, dict] = {}
    plain: list[dict] = []

    for m in markets:
        dm = DRAW_RE.match(m.get("question") or "")
        if dm:
            key = frozenset([dm.group(1), dm.group(2)])
            soccer.setdefault(key, {"teams": (dm.group(1), dm.group(2))})
            soccer[key]["draw"] = (_prices(m), _f(m.get("volume")))
            soccer[key]["created"] = m.get("createdAt")

    for m in markets:
        q = m.get("question") or ""
        if DRAW_RE.match(q):
            continue
        wm = WIN_RE.match(q)
        hit = None
        if wm:
            team = wm.group(1)
            hit = next((key for key in soccer if team in key), None)
            if hit is not None:
                soccer[hit][team] = (_prices(m), _f(m.get("volume")))
        if hit is None:
            plain.append({
                "kind": "plain", "created": m.get("createdAt"), "question": q,
                "outs": _outcomes(m), "prices": _prices(m), "volume": _f(m.get("volume")),
            })

    merged = []
    for key, d in soccer.items():
        t1, t2 = d.get("teams", tuple(key))
        merged.append({
            "kind": "soccer3", "created": d.get("created"),
            "teams": (t1, t2), "p1": d.get(t1), "p2": d.get(t2), "draw": d.get("draw"),
        })
    return merged + plain


def flag_templated(rows: list[dict]) -> None:
    """Mark rows whose exact price-signature repeats often with no volume —
    that's a default/template line handed out at market creation, not a
    market-discovered price. Doesn't mean "no opportunity", just "no one has
    traded this yet so the number isn't evidence of anything either way"."""
    sigs = Counter(
        tuple(round(p, 4) for p in r["prices"])
        for r in rows if r["kind"] == "plain" and r["prices"] and not r["volume"]
    )
    for r in rows:
        r["templated"] = bool(
            r["kind"] == "plain" and r["prices"] and not r["volume"]
            and sigs[tuple(round(p, 4) for p in r["prices"])] >= 4
        )


def render_moneyline(rows: list[dict]) -> str:
    lines = [f"candidates: {len(rows)}"]
    for r in rows:
        date = (r["created"] or "")[:10]
        if r["kind"] == "soccer3":
            t1, t2 = r["teams"]
            p1 = r["p1"][0][0] if r["p1"] and r["p1"][0] else None
            p2 = r["p2"][0][0] if r["p2"] and r["p2"][0] else None
            pd = r["draw"][0][0] if r["draw"] and r["draw"][0] else None
            v1, v2, vd = (r["p1"][1] if r["p1"] else 0) or 0, (r["p2"][1] if r["p2"] else 0) or 0, (r["draw"][1] if r["draw"] else 0) or 0
            vol_s = "none" if not (v1 or v2 or vd) else f"{v1 + v2 + vd:.0f}"
            lines.append(f"- {date} {t1} {p1} - {t2} {p2} (draw {pd}) vol={vol_s}")
        else:
            outs, prices, vol = r["outs"], r["prices"], r["volume"]
            vol_s = "none" if not vol else (f"{vol:.0f}" if vol >= 1 else f"{vol:.2f}")
            scores = f"{outs[0]} {prices[0]} - {outs[1]} {prices[1]}" if len(outs) == 2 and len(prices) == 2 \
                else " / ".join(f"{o} {p}" for o, p in zip(outs, prices))
            tag = " [templated]" if r.get("templated") else ""
            lines.append(f"- {date} {r['question']} = {scores} vol={vol_s}{tag}")
    return "\n".join(lines) + "\n"


def run_moneyline(args) -> int:
    install_doh_override()
    markets = fetch_moneyline_since(args.since, args.max_pages)
    rows = merge_moneyline_rows(markets)
    flag_templated(rows)
    rows.sort(key=lambda r: r["created"] or "", reverse=True)
    print(render_moneyline(rows))
    return 0


# =============================================================================
# tagged subcommand — /events + tag_slug engine (elections)
# =============================================================================

PRESETS = {
    "early": dict(order="createdAt", require_vs=True, min_lifespan=0,
                  min_days_left=2, fav_min=0.50, fav_max=0.72,
                  max_spread=0.10, min_volume=3000),
    "fresh": dict(order="createdAt", require_vs=False, min_lifespan=0,
                  min_days_left=1, fav_min=0.0, fav_max=1.0,
                  max_spread=0.12, min_volume=0),
    "band": dict(order="volume24hr", require_vs=False, min_lifespan=0,
                 min_days_left=2, fav_min=0.50, fav_max=0.65,
                 max_spread=0.12, min_volume=20000),
    "raw": dict(order="createdAt", require_vs=False, min_lifespan=0,
                min_days_left=0, fav_min=0.0, fav_max=1.0,
                max_spread=1.0, min_volume=0),
}
BASE = dict(order="createdAt", require_vs=False, min_lifespan=0, min_days_left=0,
            fav_min=0.0, fav_max=1.0, max_spread=1.0, min_volume=0)


def fetch_tagged_events(tag: str, order: str, limit: int) -> list[dict]:
    return _get("/events", {
        "tag_slug": tag, "related_tags": "true", "active": "true",
        "closed": "false", "order": order, "ascending": "false", "limit": str(limit),
    })


def _dt(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def analyze_tagged(events: list[dict], cfg: dict, now: datetime) -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for ev in events:
        et = ev.get("title") or ""
        for m in ev.get("markets") or []:
            slug = m.get("slug")
            if not slug or slug in seen:
                continue
            seen.add(slug)

            q = m.get("question") or ""
            ql = q.lower()
            if cfg["require_vs"] and " vs" not in et.lower() and " vs" not in ql:
                continue

            try:
                outs = json.loads(m.get("outcomes") or "[]")
                prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if len(outs) != 2 or len(prices) != 2:
                continue

            bid, ask, spread = _f(m.get("bestBid")), _f(m.get("bestAsk")), _f(m.get("spread"))
            if bid is None or ask is None or spread is None:
                continue
            if spread > cfg["max_spread"]:
                continue

            fav = max(prices)
            if not (cfg["fav_min"] <= fav <= cfg["fav_max"]):
                continue

            volume = _f(m.get("volume")) or 0.0
            if volume < cfg["min_volume"]:
                continue

            cd, ed = _dt(m.get("createdAt")), _dt(m.get("endDate"))
            lifespan = (ed - cd).days if cd and ed else None
            days_left = (ed - now).days if ed else None
            opened_ago = (now - cd).days if cd else None
            if cfg["min_lifespan"] and (lifespan is None or lifespan < cfg["min_lifespan"]):
                continue
            if cfg["min_days_left"] and (days_left is None or days_left < cfg["min_days_left"]):
                continue

            fav_idx = 0 if prices[0] >= prices[1] else 1
            rows.append({
                "question": q, "event": et, "favorite": outs[fav_idx], "favPrice": round(fav, 3),
                "bestBid": bid, "bestAsk": ask, "spread": round(spread, 3),
                "openedAgoDays": opened_ago, "lifespanDays": lifespan, "daysToResolution": days_left,
                "volume": round(volume), "slug": slug, "createdAt": m.get("createdAt"),
            })
    return rows


def render_tagged_yaml(rows: list[dict]) -> str:
    if not rows:
        return "candidates: []\n"
    lines = ["candidates:"]
    for r in rows:
        lines.append(f"  - question: {json.dumps(r['question'], ensure_ascii=False)}")
        for k in ("favorite", "favPrice", "bestBid", "bestAsk", "spread",
                  "openedAgoDays", "lifespanDays", "daysToResolution", "volume", "slug", "createdAt"):
            lines.append(f"    {k}: {json.dumps(r[k], ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def run_tagged(args) -> int:
    preset = PRESETS.get(args.mode, {})
    cfg = {}
    for k in BASE:
        explicit = getattr(args, k, None)
        cfg[k] = explicit if explicit is not None else preset.get(k, BASE[k])

    install_doh_override()
    now = datetime.now(timezone.utc)

    all_events: list[dict] = []
    for tag in [t.strip() for t in args.tags.split(",") if t.strip()]:
        try:
            all_events.extend(fetch_tagged_events(tag, cfg["order"], args.limit))
        except Exception as exc:  # one bad tag shouldn't kill the run
            print(f"# warn: tag {tag} failed: {exc}")

    rows = analyze_tagged(all_events, cfg, now)
    if cfg["order"] == "createdAt":
        rows.sort(key=lambda r: r["createdAt"] or "", reverse=True)  # newest first
    else:
        rows.sort(key=lambda r: -r["volume"])
    rows = rows[:args.max_rows]

    if args.json:
        print(json.dumps({"mode": args.mode, "config": cfg, "count": len(rows),
                          "candidates": rows}, ensure_ascii=False, indent=2))
    else:
        print(f"# mode={args.mode} tags={args.tags} -> {len(rows)} candidates")
        print(render_tagged_yaml(rows))
    return 0


# =============================================================================

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ml = sub.add_parser("moneyline", help="sports, all leagues, newest-first")
    p_ml.add_argument("--since", required=True, help="YYYY-MM-DD (UTC); include markets created on/after this date")
    p_ml.add_argument("--max-pages", type=int, default=20, help="safety cap on pagination")
    p_ml.set_defaults(func=run_moneyline)

    p_tg = sub.add_parser("tagged", help="/events+tag_slug engine (elections)")
    p_tg.add_argument("--mode", choices=list(PRESETS), default=None, help="filter preset")
    p_tg.add_argument("--tags", default="sports", help="comma-separated Polymarket tag slugs")
    p_tg.add_argument("--limit", type=int, default=40, help="events fetched per tag")
    p_tg.add_argument("--order", choices=["createdAt", "updatedAt", "endDate", "volume24hr"], default=None)
    p_tg.add_argument("--fav-min", type=float, default=None)
    p_tg.add_argument("--fav-max", type=float, default=None)
    p_tg.add_argument("--min-lifespan", type=int, default=None, help="min days between open and resolution")
    p_tg.add_argument("--min-days-left", type=int, default=None, help="min days until resolution")
    p_tg.add_argument("--max-spread", type=float, default=None, help="max bid/ask spread to count as tradeable")
    p_tg.add_argument("--min-volume", type=float, default=None, help="min total traded volume USD")
    p_tg.add_argument("--require-vs", dest="require_vs", action="store_true", default=None)
    p_tg.add_argument("--max-rows", type=int, default=None, help="cap rows printed; omit for no cap (default: print everything)")
    p_tg.add_argument("--json", action="store_true")
    p_tg.set_defaults(func=run_tagged)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

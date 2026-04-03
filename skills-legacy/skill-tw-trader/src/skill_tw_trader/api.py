from datetime import date
from typing import Optional

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from skill_tw_trader.messaging.line import handle_event, reply, verify_signature
from skill_tw_trader.core.trading_engine import build_status, get_equity_curve, _load_ledger
from skill_tw_trader.core.account_paths import DATA_DIR, JOURNALS_DIR, LESSONS_FILE, WATCHLIST_FILE, journal_path
from skill_tw_trader.core.market_service import (
    get_history_records,
    get_latest_price,
    get_market_news_raw,
    get_technical_data,
)

app = FastAPI(title="AI Trader API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoints ---

@app.get("/api/agent/state")
async def get_state():
    state_file = DATA_DIR / "state.md"
    if not state_file.exists():
        return {"content": "No state file found."}
    return {"content": state_file.read_text(encoding="utf-8")}

@app.get("/api/agent/journal")
async def get_journal(date_str: Optional[str] = None):
    d = date_str or date.today().isoformat()
    journal_file = journal_path(d)
    if not journal_file.exists():
        return {"content": None, "date": d}
    with open(journal_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {"content": data, "date": d}

@app.get("/api/agent/journals")
async def list_journals():
    if not JOURNALS_DIR.exists():
        return []
    files = sorted(JOURNALS_DIR.glob("*.yaml"), reverse=True)
    results = []
    for f in files[:10]:
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        results.append({"date": f.stem, "content": data})
    return results

@app.get("/api/agent/lessons")
async def get_lessons():
    if not LESSONS_FILE.exists():
        return {"content": "No lessons file found."}
    return {"content": LESSONS_FILE.read_text(encoding="utf-8")}

@app.get("/api/agent/watchlist")
async def get_watchlist():
    if not WATCHLIST_FILE.exists():
        return []
    with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or []

@app.get("/api/agent/posts")
async def get_posts():
    posts_dir = DATA_DIR / "posts"
    if not posts_dir.exists():
        return []
    files = sorted(posts_dir.glob("*.yaml"), reverse=True)
    results = []
    for f in files[:20]:
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if data:
            results.append(data)
    return results

@app.get("/api/market/research")
async def get_research(date_str: Optional[str] = None):
    d = date_str or date.today().isoformat()
    feed_file = DATA_DIR / "feeds" / f"{d}.yaml"
    if not feed_file.exists():
        return {"content": None, "date": d}
    with open(feed_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {"content": data, "date": d}
    
@app.get("/api/portfolio")
async def get_portfolio():
    return build_status()


@app.get("/api/portfolio/equity-history")
async def get_equity_history(days: int = 90):
    return get_equity_curve(days=days)

@app.get("/api/trades")
async def get_trades():
    raw = _load_ledger()
    return raw.get("trade_history", [])

@app.get("/api/market/quote/{symbol}")
async def get_quote(symbol: str):
    try:
        return get_latest_price(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/technical/{symbol}")
async def get_technical(symbol: str):
    try:
        return get_technical_data(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/history/{symbol}")
async def get_history(symbol: str, days: int = 100):
    try:
        return get_history_records(symbol, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/news")
async def get_news(category: str = "tw_stock", limit: int = 10):
    return get_market_news_raw(category, limit=limit)

# --- Messaging webhooks ---

@app.post("/webhook/line")
async def line_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("X-Line-Signature", "")
    if not verify_signature(body, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")
    payload = await request.json()
    for event in payload.get("events", []):
        text = handle_event(event)
        if text and event.get("replyToken"):
            result = reply(event["replyToken"], text)
            print(f"[LINE reply] {result}")
        else:
            print(f"[LINE event] no reply: text={text!r} replyToken={event.get('replyToken')!r}")
    return {"status": "ok"}


@app.get("/api/inbox")
async def get_inbox(n: int = 5):
    from skill_tw_trader.messaging.line import get_latest_inbox
    return {"content": get_latest_inbox(n)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

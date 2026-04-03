"""LINE webhook handler (passive reply) + inbox query."""
from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

import httpx
import yaml

INBOX_DIR = Path(__file__).resolve().parents[4] / "data" / "inbox"
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"


def verify_signature(body: bytes, signature: str) -> bool:
    import base64
    secret = os.environ.get("LINE_CHANNEL_SECRET", "")
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)


def reply(reply_token: str, text: str) -> dict:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        return {"ok": False, "error": "LINE_CHANNEL_ACCESS_TOKEN not set"}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"replyToken": reply_token, "messages": [{"type": "text", "text": text}]}
    resp = httpx.post(LINE_REPLY_URL, json=payload, headers=headers, timeout=10)
    return resp.json() if resp.content else {"status": resp.status_code}


def get_latest_inbox(n: int = 3) -> str:
    if not INBOX_DIR.exists():
        return "尚無紀錄"
    files = sorted(INBOX_DIR.glob("*.yaml"), reverse=True)[:n]
    if not files:
        return "尚無紀錄"
    parts = []
    for f in files:
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        ts = data.get("timestamp", f.stem)
        agent = data.get("agent", "")
        action = data.get("action", "")
        summary = data.get("summary", "").strip()
        parts.append(f"[{ts}] {agent}/{action}\n{summary}")
    return "\n\n---\n\n".join(parts)


def handle_event(event: dict) -> str | None:
    """Handle a single LINE webhook event. Returns reply text or None."""
    if event.get("type") != "message":
        return None
    msg = event.get("message", {})
    if msg.get("type") != "text":
        return None
    return get_latest_inbox(3)

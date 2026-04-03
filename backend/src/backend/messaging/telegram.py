"""Telegram push notifications (active)."""
from __future__ import annotations

import os

import httpx


def push(text: str) -> dict:
    """Push a message to Telegram. Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from env."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = httpx.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    return resp.json()

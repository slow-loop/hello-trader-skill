from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.request import Request, urlopen

from .models import MarketSnapshot

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"


def validate_llm_config() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is required to run LLM-based paper trading.")


def estimate_yes_probability(snapshot: MarketSnapshot) -> tuple[float, str]:
    validate_llm_config()
    api_key = os.environ["ANTHROPIC_API_KEY"]

    model = os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    prompt = build_probability_prompt(snapshot)
    request = Request(
        ANTHROPIC_API_URL,
        data=json.dumps(
            {
                "model": model,
                "max_tokens": 24,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": api_key,
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    content = payload.get("content", [])
    text = "\n".join(_extract_text_blocks(content)).strip()
    probability = _parse_probability(text)
    return probability, model


def build_probability_prompt(snapshot: MarketSnapshot) -> str:
    payload = {
        "question": snapshot.question,
        "market_yes": round(snapshot.yes_price, 4),
        "market_no": round(snapshot.no_price, 4),
        "volume_24h": round(snapshot.volume_24h, 2),
        "liquidity": round(snapshot.liquidity, 2),
        "best_bid_yes": snapshot.best_bid,
        "best_ask_yes": snapshot.best_ask,
        "spread_yes": snapshot.spread,
        "days_to_resolution": snapshot.days_to_resolution,
        "one_day_price_change_yes": round(snapshot.one_day_price_change, 4),
        "end_date": snapshot.end_date,
    }
    return (
        "Estimate TRUE probability (0.0-1.0) that YES resolves true.\n"
        "Use ONLY the market snapshot below.\n"
        "Do not assume any outside news or knowledge.\n"
        "Reply ONLY a number between 0 and 1.\n\n"
        f"Snapshot:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _extract_text_blocks(content: list[dict[str, Any]]) -> list[str]:
    text_blocks: list[str] = []
    for item in content:
        if item.get("type") == "text" and item.get("text"):
            text_blocks.append(str(item["text"]))
    return text_blocks


def _parse_probability(text: str) -> float:
    matches = re.findall(r"(?<!\d)(?:0(?:\.\d+)?|1(?:\.0+)?)", text)
    for match in matches:
        value = float(match)
        if 0.0 <= value <= 1.0:
            return value
    raise RuntimeError(f"Could not parse probability from model response: {text!r}")

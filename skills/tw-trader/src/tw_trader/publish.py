"""Publish pipeline — render daily artifacts (poster, etc.) from post.yaml + backend2 state."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import yaml
from PIL import Image, ImageDraw, ImageFont

BACKEND_URL = os.getenv("TRADER_BACKEND_URL", "http://localhost:8000")

# Poster layout (portrait, 4:5 for Threads/IG)
CANVAS_SIZE = (1080, 1350)
MARGIN = 72
BG_COLOR = (250, 250, 248)
TEXT_COLOR = (32, 32, 36)
MUTED_COLOR = (120, 120, 128)
ACCENT_COLOR = (198, 54, 54)
ACCENT_GREEN = (38, 128, 78)

# Font candidates — first that exists wins.
FONT_CANDIDATES: list[str] = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]

POST_EXCERPT_CHARS = 220


def _pick_font_path() -> str:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    raise RuntimeError(
        "No CJK-capable font found. Install one of: " + ", ".join(FONT_CANDIDATES)
    )


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_pick_font_path(), size=size)


def _api_get(path: str) -> dict[str, Any]:
    url = f"{BACKEND_URL}{path}"
    try:
        r = httpx.get(url, timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"backend2 GET {path} failed: {exc}") from exc


def _publish_root() -> Path:
    # publish.py -> tw_trader -> src -> tw-trader(package root)
    return Path(__file__).resolve().parents[2] / "data" / "publish"


def _resolve_date(date_arg: str | None) -> str:
    if date_arg in (None, "today", ""):
        return date.today().isoformat()
    return date_arg


def _load_post_yaml(day_dir: Path) -> dict[str, Any]:
    post_file = day_dir / "post.yaml"
    if not post_file.exists():
        raise FileNotFoundError(f"No post.yaml at {post_file}")
    data = yaml.safe_load(post_file.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{post_file} is not a mapping")
    return data


def _excerpt(text: str, limit: int = POST_EXCERPT_CHARS) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Greedy CJK-aware wrap: treat every char as a potential break point."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for ch in paragraph:
            candidate = current + ch
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
    return lines


def _today_realized_pnl(trades: list[dict[str, Any]]) -> float:
    total = 0.0
    for t in trades:
        pnl = t.get("pnl")
        if pnl is not None:
            total += float(pnl)
    return total


def render_poster(date_arg: str | None = None, output: Path | None = None) -> Path:
    """Render poster.png for a given date using post.yaml + /account."""
    day = _resolve_date(date_arg)
    day_dir = _publish_root() / day
    post = _load_post_yaml(day_dir)
    posts = post.get("posts") or []
    if not posts:
        raise ValueError(f"{day_dir/'post.yaml'} has no posts")
    first_text = str(posts[0].get("text", "")).strip()
    if not first_text:
        raise ValueError("first post has no text")

    account = _api_get("/account")
    account_value = float(account.get("account_value", 0) or 0)
    realized_today = _today_realized_pnl(account.get("today_trades") or [])
    position_count = len(account.get("positions") or [])
    workspace_name = str(account.get("name", "tw-trader"))

    img = Image.new("RGB", CANVAS_SIZE, BG_COLOR)
    draw = ImageDraw.Draw(img)

    title_font = _font(52)
    subtitle_font = _font(30)
    body_font = _font(40)
    number_label_font = _font(26)
    number_font = _font(64)

    # Header: date + workspace name
    draw.text((MARGIN, MARGIN), day, font=title_font, fill=TEXT_COLOR)
    draw.text(
        (MARGIN, MARGIN + 70),
        workspace_name,
        font=subtitle_font,
        fill=MUTED_COLOR,
    )

    # Divider
    divider_y = MARGIN + 130
    draw.line(
        [(MARGIN, divider_y), (CANVAS_SIZE[0] - MARGIN, divider_y)],
        fill=MUTED_COLOR,
        width=2,
    )

    # Body: post excerpt
    body_text = _excerpt(first_text)
    body_lines = _wrap_text(draw, body_text, body_font, CANVAS_SIZE[0] - 2 * MARGIN)
    y = divider_y + 48
    line_height = int(body_font.size * 1.5)
    for line in body_lines:
        draw.text((MARGIN, y), line, font=body_font, fill=TEXT_COLOR)
        y += line_height

    # Numbers row (pinned near bottom)
    row_top = CANVAS_SIZE[1] - MARGIN - 180
    draw.line(
        [(MARGIN, row_top - 30), (CANVAS_SIZE[0] - MARGIN, row_top - 30)],
        fill=MUTED_COLOR,
        width=2,
    )

    col_width = (CANVAS_SIZE[0] - 2 * MARGIN) // 3
    cols = [
        ("帳戶總額", f"{account_value:,.0f}", TEXT_COLOR),
        (
            "今日已實現",
            f"{realized_today:+,.0f}",
            ACCENT_GREEN if realized_today >= 0 else ACCENT_COLOR,
        ),
        ("持倉數", f"{position_count}", TEXT_COLOR),
    ]
    for i, (label, value, color) in enumerate(cols):
        cx = MARGIN + col_width * i
        draw.text((cx, row_top), label, font=number_label_font, fill=MUTED_COLOR)
        draw.text((cx, row_top + 36), value, font=number_font, fill=color)

    # Footer
    footer = f"channel: {post.get('channel', '-')}"
    draw.text(
        (MARGIN, CANVAS_SIZE[1] - MARGIN - 8 - number_label_font.size),
        footer,
        font=number_label_font,
        fill=MUTED_COLOR,
    )

    output_path = output or (day_dir / "poster.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    return output_path


def main(date_arg: str | None = None) -> int:
    try:
        path = render_poster(date_arg)
    except Exception as exc:
        print(f"publish failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))

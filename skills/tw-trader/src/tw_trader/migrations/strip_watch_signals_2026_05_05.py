"""One-shot migration v2: strip watch_signals + trigger_price.

After the rename in v1, we decided that pre-computed entry signals add
no value over the analysis report — and turning them into a gate
re-introduces the failure mode they were meant to fix. Removing them
entirely.

Drops per item:
  - watch_signals
  - trigger_price

Keeps:
  - invalidation_signals  (still automatic — kill conditions)
  - invalidation_price    (convenience shortcut for invalidation)

Run:
    cd skills/tw-trader && uv run python -m tw_trader.migrations.strip_watch_signals_2026_05_05

Backs up the original. Idempotent.
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime

import yaml

from tw_trader.workspace import watchlist_path


DROP_KEYS = ("watch_signals", "trigger_price")


def migrate_item(item: dict) -> tuple[dict, list[str]]:
    changes: list[str] = []
    new_item = dict(item)
    for key in DROP_KEYS:
        if key in new_item:
            new_item.pop(key)
            changes.append(f"dropped {key}")
    return new_item, changes


def main() -> int:
    path = watchlist_path()
    if not path.exists():
        print(f"watchlist not found: {path}", file=sys.stderr)
        return 1

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        print(f"watchlist must be a list at top level: {path}", file=sys.stderr)
        return 1

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak.{timestamp}")
    shutil.copy2(path, backup)

    new_items: list[dict] = []
    total = 0
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            print(f"skip non-mapping item at index {idx}", file=sys.stderr)
            new_items.append(item)
            continue
        migrated, changes = migrate_item(item)
        new_items.append(migrated)
        if changes:
            total += len(changes)
            print(f"[{migrated.get('symbol', '?')}] {'; '.join(changes)}")

    if total == 0:
        print("no changes — already stripped.")
        backup.unlink()
        return 0

    serialized = yaml.safe_dump(
        new_items,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    path.write_text(serialized, encoding="utf-8")
    print(f"\nstripped {total} field(s) across {len(new_items)} item(s).")
    print(f"backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

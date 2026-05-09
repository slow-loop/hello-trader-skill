"""One-shot migration for the watch_signals / invalidation_signals rename
and the removal of the ``ready`` watchlist status.

Renames per item:
  - trigger_conditions      -> watch_signals
  - invalidation_conditions -> invalidation_signals

Status migration:
  - ready -> watch  (Trading no longer reads `ready`; `signals_active`
                     evaluation drives attention now.)

Run from repo root:
    cd skills/tw-trader && uv run python -m tw_trader.migrations.rename_signals_2026_05_05

Backs up the original to ``watchlist.yaml.bak.<timestamp>`` before writing.
Idempotent: re-running on an already-migrated file is a no-op.
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

from tw_trader.workspace import watchlist_path


RENAME_PAIRS = (
    ("trigger_conditions", "watch_signals"),
    ("invalidation_conditions", "invalidation_signals"),
)


def migrate_item(item: dict) -> tuple[dict, list[str]]:
    """Return (new_item, list_of_changes) for a single watchlist item."""
    changes: list[str] = []
    new_item = dict(item)

    for old_key, new_key in RENAME_PAIRS:
        if old_key in new_item:
            if new_key in new_item and new_item[new_key]:
                # Both keys present and new key non-empty — prefer new key, drop old.
                changes.append(f"{old_key} dropped (kept existing {new_key})")
                new_item.pop(old_key)
            else:
                new_item[new_key] = new_item.pop(old_key)
                changes.append(f"{old_key} -> {new_key}")

    if new_item.get("status") == "ready":
        new_item["status"] = "watch"
        changes.append("status: ready -> watch")

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
    total_changes = 0
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            print(f"skip non-mapping item at index {idx}", file=sys.stderr)
            new_items.append(item)
            continue
        migrated, changes = migrate_item(item)
        new_items.append(migrated)
        if changes:
            total_changes += len(changes)
            print(f"[{migrated.get('symbol', '?')}] {'; '.join(changes)}")

    if total_changes == 0:
        print("no changes — already migrated.")
        backup.unlink()
        return 0

    serialized = yaml.safe_dump(
        new_items,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    path.write_text(serialized, encoding="utf-8")
    print(f"\nmigrated {total_changes} field(s) across {len(new_items)} item(s).")
    print(f"backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

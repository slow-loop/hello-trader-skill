"""Workspace / paths / active-strategy resolution for us-trader."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

SKILL_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Workspace:
    account: str
    skill_root: Path

    @property
    def account_dir(self) -> Path:
        return self.skill_root / "data" / "accounts" / self.account

    @property
    def strategies_dir(self) -> Path:
        return self.skill_root / "data" / "strategies"

    @property
    def active_manifest(self) -> Path:
        return self.strategies_dir / "ACTIVE.yaml"

    @property
    def ledger_path(self) -> Path:
        return self.account_dir / "state" / "ledger.json"

    @property
    def equity_path(self) -> Path:
        return self.account_dir / "state" / "equity.json"

    def journal_path(self, date_str: str | None = None) -> Path:
        date_str = date_str or datetime.utcnow().strftime("%Y-%m-%d")
        return self.account_dir / "journals" / f"{date_str}.yaml"

    def ensure_dirs(self) -> None:
        for p in [
            self.account_dir / "state",
            self.account_dir / "journals",
            self.account_dir / "research",
            self.account_dir / "market_snapshots",
            self.strategies_dir,
        ]:
            p.mkdir(parents=True, exist_ok=True)


def resolve_active_strategy(ws: Workspace) -> Path:
    """Find the active strategy YAML file for this workspace."""
    manifest = ws.active_manifest
    if manifest.exists():
        data = yaml.safe_load(manifest.read_text())
        fname = data.get("file")
        if fname:
            path = ws.strategies_dir / fname
            if path.exists():
                return path
    # Fallback: any *.yaml in strategies/ sorted newest first
    candidates = sorted(
        [p for p in ws.strategies_dir.glob("*.yaml") if p.name != "ACTIVE.yaml"],
        reverse=True,
    )
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        f"no active strategy found in {ws.strategies_dir}; run `lab promote` first"
    )

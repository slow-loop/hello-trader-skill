#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = APP_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from skill_poly_trader.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

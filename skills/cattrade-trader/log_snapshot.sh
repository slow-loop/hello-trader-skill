#!/bin/bash
set -e
SKILL_DIR="/Users/cw/Documents/GitHub/hello-trader-skill/skills/cattrade-trader"
LOG="$SKILL_DIR/data/snapshots.jsonl"
ERR="$SKILL_DIR/data/errors.log"

cd "$SKILL_DIR"
/Users/cw/.local/bin/uv run cattrade scan --json --top-n 20 >> "$LOG" 2>> "$ERR"

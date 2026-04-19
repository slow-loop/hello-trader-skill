#!/bin/bash
# 每 3 分鐘 fetch 一次 cattrade sheet，append JSON 到 snapshots.jsonl
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$SKILL_DIR/data/snapshots.jsonl"
ERR="$SKILL_DIR/data/errors.log"

mkdir -p "$SKILL_DIR/data"
echo "[$(date)] watch started" >> "$ERR"

while true; do
  /Users/cw/.local/bin/uv run --project "$SKILL_DIR" cattrade scan --json --top-n 20 >> "$LOG" 2>> "$ERR"
  echo "" >> "$LOG"   # newline separator
  sleep 180
done

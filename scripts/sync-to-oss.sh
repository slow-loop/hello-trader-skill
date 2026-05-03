#!/usr/bin/env bash
# Sync the clean OSS subset from this private repo to nano-trader-skills.
#
# Usage:
#   ./scripts/sync-to-oss.sh [DEST]
#
# DEST defaults to ../nano-trader-skills (sibling dir).
# The destination must already exist (created by `git init` or `git clone` of
# the empty github repo). This script overwrites tracked files but never
# deletes files that aren't in the source — review with `git status` after.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$SRC/../nano-trader-skills}"

if [[ ! -d "$DEST" ]]; then
  echo "DEST '$DEST' does not exist. Create it first:"
  echo "  mkdir -p '$DEST' && cd '$DEST' && git init"
  exit 1
fi

echo "syncing $SRC  -->  $DEST"
echo

# Shared excludes applied to every rsync call.
COMMON_EXCLUDES=(
  --exclude='.DS_Store'
  --exclude='.venv/'
  --exclude='__pycache__/'
  --exclude='*.egg-info/'
  --exclude='.pytest_cache/'
  --exclude='node_modules/'
  --exclude='dist/'
  --exclude='build/'
  --exclude='.env'
  --exclude='.web-reader/'
  --exclude='.claude/'
  --exclude='tmp/'
  --exclude='*.log'
)

run_rsync() {
  local rel="$1"
  shift
  mkdir -p "$DEST/$rel"
  rsync -a --delete --delete-excluded "${COMMON_EXCLUDES[@]}" "$@" \
    "$SRC/$rel/" "$DEST/$rel/"
  echo "  ✓ $rel"
}

# 1) libs/market-core (full)
#    Note: web-reader is no longer in this repo — pulled from
#    github.com/w121211/web-reader via pyproject.toml.
run_rsync "libs/market-core"

# 2) skills/tw-trader — code + prompts + static config only.
#    Runtime state lives at repo-root data/, not under the skill anymore.
run_rsync "skills/tw-trader"

# 3) data/ — keep templates only; everything else is private runtime state.
run_rsync "data" \
  --exclude='account/journals/' \
  --exclude='account/screener/' \
  --exclude='account/state/' \
  --exclude='account/events.jsonl' \
  --exclude='account/lessons.md' \
  --exclude='account/watchlist.yaml' \
  --exclude='posts/' \
  --include='account/research/template/***' \
  --include='account/research/' \
  --exclude='account/research/*' \
  --include='account/trading-cards/template/***' \
  --include='account/trading-cards/' \
  --exclude='account/trading-cards/*'

# 4) frontend-nano (full minus build artefacts)
run_rsync "frontend-nano"

# 5) Top-level files
for f in README.md README.zh-TW.md LICENSE .gitignore .env.example; do
  if [[ -f "$SRC/$f" ]]; then
    cp "$SRC/$f" "$DEST/$f"
    echo "  ✓ $f"
  fi
done

echo
echo "done. next:"
echo "  cd '$DEST'"
echo "  git status                       # review"
echo "  rg -uu --hidden 'YAHOO|FUGLE|FINMIND|w121' .   # final secret sweep"
echo "  git add -A && git commit -m 'sync from upstream'"
echo "  git push"

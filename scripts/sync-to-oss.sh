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
  rsync -a --delete-excluded "${COMMON_EXCLUDES[@]}" "$@" \
    "$SRC/$rel/" "$DEST/$rel/"
  echo "  ✓ $rel"
}

# 1) libs/web-reader  (full, minus secrets/cache)
run_rsync "libs/web-reader"

# 2) libs/market-core (full)
run_rsync "libs/market-core"

# 3) skills/tw-trader — code + prompts + config + templates ONLY.
#    All real account data (journals, research, screener, state, posts,
#    publish, watchlist, lessons, events) is excluded.
run_rsync "skills/tw-trader" \
  --exclude='data/account/journals/' \
  --exclude='data/account/screener/' \
  --exclude='data/account/state/' \
  --exclude='data/account/events.jsonl' \
  --exclude='data/account/lessons.md' \
  --exclude='data/account/watchlist.yaml' \
  --exclude='data/posts/' \
  --exclude='data/publish/' \
  --include='data/account/research/template/***' \
  --include='data/account/research/' \
  --exclude='data/account/research/*' \
  --include='data/account/trading-cards/template/***' \
  --include='data/account/trading-cards/' \
  --exclude='data/account/trading-cards/*'

# 4) frontend-nano (full minus build artefacts)
run_rsync "frontend-nano"

# 5) Top-level files
for f in README.md LICENSE .gitignore; do
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

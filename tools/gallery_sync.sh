#!/bin/bash
# gallery_sync.sh — one-shot: rebuild the gallery and push if anything changed.
#
# Called by gallery_watch.sh whenever a change is detected in the Drive source
# folder. Idempotent: build_gallery.py's SHA1 cache means unchanged photos
# are skipped, and git only commits when the working tree actually differs.
set -euo pipefail

REPO="/Users/qphirosuke/Desktop/git/HomePage"
LOG="$REPO/tools/gallery_sync.log"

mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1

echo "---- $(date '+%Y-%m-%d %H:%M:%S') sync start ----"

cd "$REPO"

# 1. Build (resize new photos, update gallery.json, inline into gallery.html)
if ! /usr/bin/env python3 tools/build_gallery.py; then
    echo "ERROR: build_gallery.py failed"
    exit 1
fi

# 2. Stage anything the build touched
git add Gallery/ gallery.html tools/.gallery_cache.json 2>/dev/null || true

# 3. Only commit if the index differs from HEAD
if git diff --cached --quiet; then
    echo "no changes to commit"
    exit 0
fi

# 4. Commit + push. Short summary of what moved; details go in the log.
SUMMARY=$(git diff --cached --name-status | awk '{print $1" "$2}' | head -8)
git commit -m "gallery: auto-sync from Drive

$SUMMARY

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"

if git push origin main; then
    echo "pushed."
else
    echo "ERROR: push failed (check auth)"
    exit 1
fi

#!/bin/bash
# gallery_watch.sh — watch the Drive Gallery folder; sync on change.
#
# Uses fswatch (recursive). Debounces: after a filesystem event, waits
# DEBOUNCE_SECS of quiet before running the sync, so a batch of file
# writes (e.g. uploading several photos at once) only triggers one build.
#
# Run via LaunchAgent for always-on behaviour, or manually in a terminal.
set -euo pipefail

DRIVE_GALLERY="/Users/qphirosuke/Library/CloudStorage/GoogleDrive-hirosuke.asahi@star.rcast.u-tokyo.ac.jp/マイドライブ/Homepage/Gallery"
SYNC_SCRIPT="/Users/qphirosuke/Desktop/git/HomePage/tools/gallery_sync.sh"
LOG="/Users/qphirosuke/Desktop/git/HomePage/tools/gallery_watch.log"
DEBOUNCE_SECS=20

mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1

echo "---- $(date '+%Y-%m-%d %H:%M:%S') watcher starting ----"
echo "watching: $DRIVE_GALLERY"

if [[ ! -d "$DRIVE_GALLERY" ]]; then
    echo "ERROR: watch target does not exist (Drive not mounted?)"
    exit 1
fi

if ! command -v fswatch >/dev/null; then
    echo "ERROR: fswatch not installed. Install with: brew install fswatch"
    exit 1
fi

# fswatch emits one event per filesystem change; we batch them with a timer.
# The subshell maintains a pending flag; whenever an event arrives we reset
# the countdown. When the countdown expires with no new events, we sync.
LAST_EVENT_FILE=$(mktemp -t gallery_watch.XXXXXX)
echo "0" > "$LAST_EVENT_FILE"

# Debouncer background loop
(
    while true; do
        last=$(cat "$LAST_EVENT_FILE" 2>/dev/null || echo "0")
        if [[ "$last" != "0" ]]; then
            now=$(date +%s)
            elapsed=$((now - last))
            if (( elapsed >= DEBOUNCE_SECS )); then
                echo "$(date '+%H:%M:%S') change settled → sync"
                echo "0" > "$LAST_EVENT_FILE"
                "$SYNC_SCRIPT" || echo "sync returned nonzero"
            fi
        fi
        sleep 5
    done
) &
DEBOUNCER_PID=$!
trap 'kill $DEBOUNCER_PID 2>/dev/null; rm -f "$LAST_EVENT_FILE"; echo "watcher stopping"; exit 0' EXIT INT TERM

# fswatch loop: on every event, stamp the time
# --latency 2 smooths out burst events; -r recurses into subdirs
fswatch --latency 2 -r "$DRIVE_GALLERY" | while read -r changed; do
    date +%s > "$LAST_EVENT_FILE"
done

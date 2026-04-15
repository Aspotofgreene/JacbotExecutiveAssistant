#!/bin/bash
# update.sh — pull latest code from GitHub and restart Jacbot
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.jacbot.assistant.plist"
BRANCH="claude/flexible-task-input-dyWG6"

cd "$(dirname "$0")"

echo "Stopping Jacbot..."
launchctl unload "$PLIST" 2>/dev/null || true

echo "Pulling latest code..."
git fetch origin
git checkout -- run.sh 2>/dev/null || true   # discard any local run.sh edits
git pull origin "$BRANCH"

echo "Starting Jacbot..."
launchctl load "$PLIST"

echo ""
echo "Done! Jacbot is back up. Check logs with:"
echo "  tail -f ~/Library/Logs/jacbot.log"

#!/bin/bash
# Jacbot startup wrapper — activates the venv (if present) and launches the bot.
# Used by the macOS LaunchAgent to start Jacbot at login.
set -euo pipefail

cd "$(dirname "$0")"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

exec python -m jacbot.main

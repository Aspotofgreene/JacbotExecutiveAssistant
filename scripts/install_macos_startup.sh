#!/bin/bash
# install_macos_startup.sh
# Installs a macOS LaunchAgent so Jacbot starts automatically at login.
#
# Usage (run from any directory):
#   bash scripts/install_macos_startup.sh
#
# To uninstall:
#   launchctl unload ~/Library/LaunchAgents/com.jacbot.assistant.plist
#   rm ~/Library/LaunchAgents/com.jacbot.assistant.plist
set -euo pipefail

LABEL="com.jacbot.assistant"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/$LABEL.plist"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$HOME/Library/Logs"

echo "=== Jacbot macOS startup installer ==="
echo "Project:  $PROJECT_DIR"
echo "Plist:    $PLIST_PATH"
echo ""

# Validate run.sh exists
if [ ! -f "$PROJECT_DIR/run.sh" ]; then
    echo "ERROR: run.sh not found at $PROJECT_DIR/run.sh"
    exit 1
fi

# Ensure run.sh is executable
chmod +x "$PROJECT_DIR/run.sh"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Create LaunchAgents directory if needed
mkdir -p "$PLIST_DIR"

# Unload existing service if it's already loaded (suppress error if not loaded)
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Write the plist
cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PROJECT_DIR/run.sh</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <!-- Start immediately when you log in -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Restart automatically if the bot crashes -->
    <key>KeepAlive</key>
    <true/>

    <!-- Wait 30s before restarting after a crash (prevents rapid restart loops) -->
    <key>ThrottleInterval</key>
    <integer>30</integer>

    <!-- Log stdout and stderr to ~/Library/Logs/ -->
    <key>StandardOutPath</key>
    <string>$LOG_DIR/jacbot.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/jacbot.error.log</string>
</dict>
</plist>
PLIST

echo "Plist written to $PLIST_PATH"

# Load the service
launchctl load "$PLIST_PATH"
echo "Service loaded — Jacbot will now start at login and restart if it crashes."
echo ""
echo "Useful commands:"
echo "  View logs:    tail -f ~/Library/Logs/jacbot.log"
echo "  Stop now:     launchctl unload $PLIST_PATH"
echo "  Start now:    launchctl load $PLIST_PATH"
echo "  Uninstall:    launchctl unload $PLIST_PATH && rm $PLIST_PATH"

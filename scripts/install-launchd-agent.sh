#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_DST="$HOME/Library/LaunchAgents/com.ashish.env-notes.plist"
DATA_ROOT="${ENV_NOTES_DATA_ROOT:-$HOME/Documents/env-notes-private/notebooks}"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$REPO_ROOT/logs"

cat > "$PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ashish.env-notes</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd "$REPO_ROOT"; /opt/homebrew/bin/uv run python -m env_notes</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$REPO_ROOT</string>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>$REPO_ROOT/logs/env-notes.out.log</string>

  <key>StandardErrorPath</key>
  <string>$REPO_ROOT/logs/env-notes.err.log</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>ENV_NOTES_DATA_ROOT</key>
    <string>$DATA_ROOT</string>
  </dict>
</dict>
</plist>
EOF

plutil -lint "$PLIST_DST"
launchctl bootout "gui/$(id -u)" "$PLIST_DST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl kickstart -k "gui/$(id -u)/com.ashish.env-notes"

echo "LaunchAgent installed and started: com.ashish.env-notes"
echo "Repo root: $REPO_ROOT"
echo "Data root: $DATA_ROOT"

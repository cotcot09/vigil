#!/usr/bin/env bash
set -euo pipefail
LABEL="com.notte.serve"
launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "Notte agent removed. Collected data in ~/.notte is untouched."

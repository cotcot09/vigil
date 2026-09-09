#!/usr/bin/env bash
set -euo pipefail
LABEL="com.vigil.serve"
launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "Vigil agent removed. Collected data in ~/.vigil is untouched."

#!/usr/bin/env bash
# Keeps the summary reachable by the phone, permanently, with no terminal open.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.vigil.serve"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "python3 is not on your PATH, so there is nothing to run." >&2
  echo "Install Apple's command line tools, then run this again:" >&2
  echo "    xcode-select --install" >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.vigil"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$ROOT/cli/vigil-serve.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$HOME/.vigil/serve.log</string>
  <key>StandardErrorPath</key><string>$HOME/.vigil/serve.log</string>
</dict>
</plist>
PLIST

# bootout is asynchronous: bootstrapping too soon fails with EIO, which reads
# like a permissions problem and is not. Wait for the label to actually go.
launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
for _ in $(seq 1 30); do
  launchctl print "gui/$UID/$LABEL" >/dev/null 2>&1 || break
  sleep 0.2
done

launchctl bootstrap "gui/$UID" "$PLIST" 2>/dev/null ||   launchctl kickstart -k "gui/$UID/$LABEL" 2>/dev/null || true
launchctl enable "gui/$UID/$LABEL" 2>/dev/null || true

for _ in $(seq 1 25); do
  if curl -fsS --max-time 1 http://127.0.0.1:7391/health >/dev/null 2>&1; then
    echo "Vigil is serving on this Mac and will start again at login."
    echo "Open the Vigil app on a phone on the same Wi-Fi — it finds this Mac by itself."
    exit 0
  fi
  sleep 0.2
done

echo "Agent installed but not answering yet. Check: tail ~/.vigil/serve.log" >&2
exit 1

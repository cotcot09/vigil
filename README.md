# Vigil

Records **when you work**, not what you write — and feeds the Vigil iOS app.

It reads Claude Code's own transcripts in `~/.claude/projects/`, which already
carry a timestamp on every record, and derives five-minute activity bins and a
count of typed prompts. Nothing is installed into your session and there are no
hooks — so there is nothing that can silently stop recording.

```
37h 25m · 351 prompts · 17 days · 7 projects
Peak 1 AM · 52% between 10 PM and 6 AM
```

## Install

```bash
git clone https://github.com/cotcot09/vigil ~/.claude/skills/vigil
```

Restart Claude Code, then say **“set up vigil”**.

That is the whole setup. The bundled skill starts a background service and
confirms it. Your existing transcripts are read immediately, so the dial is
populated on first launch instead of empty.

Open the app on a phone on the same Wi-Fi. It finds the Mac by itself.

## What it keeps

Timestamps, and numbers derived from them. `~/.vigil/index.json` holds a byte
offset per transcript plus the activity bins and prompt count found so far, so
each run only reads what is new — about a second cold, about 30 ms after that.

## What it never keeps

Prompt text · assistant replies · file contents · file paths · shell commands ·
tool arguments.

Transcripts are parsed for timestamps and discarded. Nothing is copied, nothing
is uploaded, and there is no network code outside the local-network server.

## Why there is no pairing code

The Mac advertises `_vigil._tcp` over Bonjour and serves ~370 bytes of JSON on
the local network. The app browses for that service and fetches it. No relay,
no account, no cloud — if the two devices are not on the same network, nothing
happens at all.

That makes the privacy claim structural rather than a promise.

## By hand

```bash
~/.claude/skills/vigil/agent/install-agent.sh   # serve at login, no terminal
~/.claude/skills/vigil/cli/vigil-summary.py     # a dial in the terminal
~/.claude/skills/vigil/cli/vigil-summary.py --days 7
~/.claude/skills/vigil/agent/uninstall-agent.sh
```

## Why five-minute bins

Wall-clock between the first and last message of a day counts lunch. A bin is
marked active only when something happened inside it, so a burst of tool calls
costs one bin and a four-hour gap costs none. That is what makes "time worked"
honest.

## Design rules

1. **One source of truth.** Transcripts. A mirror of them can only drift or
   double-count, which is exactly what an earlier hook-based version did.
2. **Nothing to install into the session.** Nothing to register means nothing
   that can fail to register.
3. **Never record content.**

## Licence

MIT

# Vigil

Records **when you work**, not what you write — and feeds the Vigil iOS app.

A Claude Code hook marks a five-minute bin active and counts the prompts you
submit. That is the entire dataset.

```
37h 25m · 351 prompts · 17 days · 7 projects
Peak 1 AM · 52% between 10 PM and 6 AM
```

## Install

```bash
git clone https://github.com/cotcot09/vigil ~/.claude/skills/vigil
```

Restart Claude Code, then say **“set up vigil”**.

That is the whole setup. Cloning into the skills directory makes Claude Code
load this as a plugin, so the hooks in `hooks/hooks.json` register themselves —
nobody edits `settings.json` and there is no block to paste. The bundled skill
then seeds from your existing transcripts and starts the background service.

Open the app on a phone on the same Wi-Fi. It finds the Mac by itself.

## What it stores

```json
{"t":1788963900,"k":"tick","p":"gold-app"}
{"t":1788964139.3,"k":"prompt","p":"gold-app"}
```

A unix timestamp, an event kind, and a folder name.

## What it never stores

Prompt text · assistant replies · file contents · file paths · shell commands ·
tool arguments · repository contents.

The collector reads the whole hook payload — unavoidable, that is how hooks
work — and discards everything except the three fields above. Session ids are
hashed before writing, so sessions can be counted but not correlated back.

## Why there is no pairing code

The Mac advertises `_vigil._tcp` over Bonjour and serves ~370 bytes of JSON on
the local network. The app browses for that service and fetches it. No relay,
no account, no cloud — if the two devices are not on the same network, nothing
happens at all.

That makes the privacy claim structural rather than a promise.

## By hand

```bash
~/.claude/skills/vigil/cli/vigil-backfill.py    # seed from existing transcripts
~/.claude/skills/vigil/agent/install-agent.sh   # serve at login, no terminal
~/.claude/skills/vigil/cli/vigil-summary.py     # a dial in the terminal
~/.claude/skills/vigil/cli/vigil-summary.py --days 7
~/.claude/skills/vigil/agent/uninstall-agent.sh
```

## Why five-minute bins

Wall-clock between the first and last message of a day counts lunch. A bin is
marked active only when something happened inside it, so 500 tool calls cost one
record and a four-hour gap costs none. It also caps the log: a full day is at
most 288 ticks, whatever you do.

## Design rules

1. **Never break a session.** Every path exits 0. A metrics collector that can
   fail a build is not worth having.
2. **Never grow without bound.** Binning happens at write time; the log rotates
   at 8 MB.
3. **Never record content.**

## Licence

MIT

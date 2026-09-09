---
name: vigil
description: Set up, check, or troubleshoot Vigil — the activity recorder that feeds the Vigil iOS app. Use when the user says "set up vigil", "connect vigil", "is vigil working", "show my vigil stats", "my hours", "when do I work", or asks why the Vigil app cannot find their Mac.
---

# Vigil

Vigil records **when** the user works — five-minute activity bins and a prompt
count — and serves that summary to the Vigil iOS app over the local network.

The hooks in this plugin register themselves. Do not edit `settings.json`.

## Setting it up

Run these in order and report what each one says.

**1. Seed from history.** Claude Code transcripts already on disk mean the app
opens with a real dial instead of an empty one.

```bash
"${CLAUDE_PLUGIN_ROOT}/cli/vigil-backfill.py"
```

**2. Keep the summary available to the phone.** This installs a LaunchAgent so
the user never has to start anything by hand again.

```bash
"${CLAUDE_PLUGIN_ROOT}/agent/install-agent.sh"
```

**3. Confirm.**

```bash
"${CLAUDE_PLUGIN_ROOT}/cli/vigil-summary.py"
```

Then tell them to open the Vigil app on a phone on the same Wi-Fi. It finds the
Mac by itself — there is no pairing code.

If the hooks have not registered yet, the session needs restarting once. Say so
plainly rather than trying to write hooks into settings.json, which is blocked
by design.

## Showing their numbers

```bash
"${CLAUDE_PLUGIN_ROOT}/cli/vigil-summary.py"            # a dial in the terminal
"${CLAUDE_PLUGIN_ROOT}/cli/vigil-summary.py" --days 7   # rolling week
```

Read the shape back to them, not just the totals. The interesting facts are the
peak hour, the share of work between 10 PM and 6 AM, and any dead hours — those
say something about how a person works that a total cannot.

## When the app cannot find the Mac

Check in this order and stop at the first failure:

1. `launchctl list | grep vigil` — is the agent loaded?
2. `curl -s localhost:7391/health` — is it serving?
3. `dns-sd -B _vigil._tcp local` — is it advertising? (Ctrl-C to stop)
4. Phone and Mac on the same Wi-Fi, and the phone not on a guest network.

The app has no cloud fallback on purpose. If discovery fails there is a real
network problem to fix, not a service to sign into.

## What it records

A unix timestamp, an event kind (`tick`, `prompt`, `session`), and a folder
name. Prompt text, file contents, paths and shell commands are read by the hook
— unavoidable, that is how hooks work — and immediately discarded. Session ids
are hashed. No network code exists in the collector.

If a user asks what is stored, show them a few real lines:

```bash
tail -3 ~/.vigil/events.jsonl
```

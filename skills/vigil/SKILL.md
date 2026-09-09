---
name: vigil
description: Set up, check, or troubleshoot Vigil — the activity recorder that feeds the Vigil iOS app. Use when the user says "set up vigil", "connect vigil", "is vigil working", "show my vigil stats", "my hours", "when do I work", or asks why the Vigil app cannot find their Mac.
---

# Vigil

Vigil reports **when** the user works by reading Claude Code's own transcripts in
`~/.claude/projects/`. Those files already carry a timestamp on every record, so
there is nothing to install into the session and nothing that can silently stop
recording. There are no hooks.

## Setting it up

One step. It installs a LaunchAgent so the summary is always reachable by the
phone, with no terminal open.

```bash
"${CLAUDE_PLUGIN_ROOT}/agent/install-agent.sh"
```

It prints an eight-character pairing code. Read it out to them — they enter it
in the app once, and it is what tells their phone which Mac is theirs.

Then confirm:

```bash
"${CLAUDE_PLUGIN_ROOT}/cli/vigil-summary.py"
```

Tell them to open the Vigil app on a phone on the same Wi-Fi. It finds the Mac
by itself — there is no pairing code and no account.

History works immediately: every transcript already on disk is included, so the
dial is populated on first launch rather than empty.

## Showing their numbers

```bash
"${CLAUDE_PLUGIN_ROOT}/cli/vigil-summary.py"            # a dial in the terminal
"${CLAUDE_PLUGIN_ROOT}/cli/vigil-summary.py" --days 7   # rolling week
```

Read the shape back, not just the totals. The peak hour, the share between
10 PM and 6 AM, and any dead hours say something about how a person works that
a total cannot.

## When the app cannot find the Mac

Check in order and stop at the first failure:

1. `launchctl list | grep vigil` — agent loaded?
2. `curl -s localhost:7391/health` — serving? (this route needs no code)
3. `curl -s "localhost:7391/summary?token=$(cat ~/.vigil/token)"` — does the
   code work? A 401 with the right code means the file and the running agent
   disagree; restart the agent.
4. `dns-sd -B _vigil._tcp local` — advertising? (Ctrl-C to stop)
5. Phone and Mac on the same Wi-Fi, phone not on a guest network. Guest
   networks often isolate clients, which no amount of configuration fixes.

If they need the code again: `cat ~/.vigil/token`

There is no cloud fallback by design. If discovery fails there is a real network
problem to fix, not a service to sign into.

## After changing the code

The LaunchAgent holds the aggregator in memory, so edits do not take effect
until it restarts:

```bash
"${CLAUDE_PLUGIN_ROOT}/agent/install-agent.sh"
```

## What it reads and what it keeps

It parses transcripts for one thing: timestamps. From those it derives
five-minute activity bins, a count of typed prompts, and the folder each session
ran in. Message content is parsed and discarded — never stored, never sent.

The index at `~/.vigil/index.json` holds byte offsets and derived numbers so
each run only reads what is new. Cold start is about a second; after that it is
about 30 ms.

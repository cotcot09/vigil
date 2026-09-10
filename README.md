# Notte

*notte* — Italian for night.

Records **when you work**, not what you write — and feeds the Notte iOS app.

It reads Claude Code's own transcripts in `~/.claude/projects/`, which already
carry a timestamp on every record, and derives five-minute activity bins and a
count of typed prompts. Nothing is installed into your session and there are no
hooks — so there is nothing that can silently stop recording.

```
37h 25m · 351 prompts · 17 days · 7 projects
Peak 1 AM · 52% between 10 PM and 6 AM
```

## Requirements

macOS with `python3` on your PATH. If `python3 --version` prints nothing,
install Apple's command line tools first — one command, no Xcode download:

```bash
xcode-select --install
```

## Install

```bash
git clone https://github.com/cotcot09/notte ~/.claude/skills/notte
```

Restart Claude Code, then say **“set up notte”**.

It prints an eight-character pairing code. Enter that in the app once.

That is the whole setup. The bundled skill starts a background service and
confirms it. Your existing transcripts are read immediately, so the dial is
populated on first launch instead of empty.

Open the app on a phone on the same Wi-Fi. It finds the Mac by itself.

## What it keeps

Timestamps, and numbers derived from them. `~/.notte/index.json` holds a byte
offset per transcript plus the activity bins and prompt count found so far, so
each run only reads what is new — about a second cold, about 30 ms after that.

## What it never keeps

Prompt text · assistant replies · file contents · file paths · shell commands ·
tool arguments.

Transcripts are parsed for timestamps and discarded. Nothing is copied, nothing
is uploaded, and there is no network code outside the local-network server.

## Why there is a pairing code

The Mac advertises `_notte._tcp` over Bonjour and serves ~370 bytes of JSON on
the local network. No relay, no account, no cloud — if the two devices are not
on the same network, nothing happens at all.

But "on the same network" includes every other machine on a cafe, office or
campus wifi, and a shared network may have several Macs running this. The code
does two jobs: it stops anyone else on the network reading your hours, and it
tells your phone which Mac is yours. The phone tries each Mac it discovers and
keeps the one that accepts your code.

The code lives in `~/.notte/token`, mode 600, generated once. Requests without
it get a 401. Delete that file to rotate it.

## By hand

```bash
~/.claude/skills/notte/agent/install-agent.sh   # serve at login, no terminal
~/.claude/skills/notte/cli/notte-summary.py     # a dial in the terminal
~/.claude/skills/notte/cli/notte-summary.py --days 7
~/.claude/skills/notte/agent/uninstall-agent.sh
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

## Support

Something not working? Open an issue:
https://github.com/cotcot09/notte/issues

Common fixes:

**The app can't find my Mac.** Both devices have to be on the same Wi-Fi, and
the Mac can't be asleep. Check the agent is running with
`launchctl list | grep com.notte.serve`.

**The pairing code doesn't work.** Codes are shown by `notte pair` and don't
expire, but re-running it prints a new one and retires the old.

**My hours look wrong.** Notte counts five-minute bins with real activity in
them, so a session you left open but idle won't be counted. See
[Why five-minute bins](#why-five-minute-bins).

**I want to start over.** Delete `~/.notte` and unpair in the app.

## Licence

MIT

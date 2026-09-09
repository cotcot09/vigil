#!/usr/bin/env python3
"""VIGIL collector — reads one Claude Code hook payload on stdin, records it.

Design rules, in order of importance:
  1. Never break the user's session. Every path exits 0, whatever happens.
  2. Never grow without bound. Activity is binned at write time, so a full day
     costs at most 288 tick records regardless of how many tools run.
  3. Never record content. Prompt text, file paths and tool arguments are read
     and discarded; only timestamps, counts and a project name are kept.
"""
import sys, os, json, time, hashlib

HOME    = os.path.expanduser("~")
ROOT    = os.environ.get("VIGIL_HOME", os.path.join(HOME, ".vigil"))
EVENTS  = os.path.join(ROOT, "events.jsonl")
STATE   = os.path.join(ROOT, "state.json")
BIN     = 300          # five minutes — the unit of "was working"
MAX_MB  = 8            # hard ceiling on the log


def _state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def _write_state(d):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f)
    os.replace(tmp, STATE)          # atomic: a killed hook can't corrupt state


def _project(cwd):
    """A stable, non-identifying label for a working directory."""
    if not cwd:
        return "unknown"
    name = os.path.basename(cwd.rstrip("/")) or "root"
    # keep the folder name (useful to the user) but not the full path
    return name[:40]


def _rotate():
    try:
        if os.path.getsize(EVENTS) > MAX_MB * 1024 * 1024:
            os.replace(EVENTS, EVENTS + ".1")
    except FileNotFoundError:
        pass


def main():
    try:
        raw = sys.stdin.read()
        ev = json.loads(raw) if raw.strip() else {}
    except Exception:
        return                                   # malformed payload: do nothing

    now     = time.time()
    kind    = ev.get("hook_event_name", "")
    project = _project(ev.get("cwd"))
    sid     = ev.get("session_id", "")

    os.makedirs(ROOT, exist_ok=True)
    st   = _state()
    rows = []

    # Exact count: one record per prompt the human actually typed.
    if kind == "UserPromptSubmit":
        rows.append({"t": round(now, 1), "k": "prompt", "p": project})

    # Session boundaries, for counting distinct sessions.
    elif kind == "SessionStart":
        rows.append({"t": round(now, 1), "k": "session", "p": project,
                     "s": hashlib.sha1(sid.encode()).hexdigest()[:12]})

    # Everything else is an activity heartbeat, collapsed to its 5-minute bin.
    # A bin already seen is dropped here rather than at read time, so the log
    # stays small no matter how tool-heavy the session is.
    b = int(now // BIN)
    if st.get("last_bin") != b:
        st["last_bin"] = b
        rows.append({"t": b * BIN, "k": "tick", "p": project})

    if not rows:
        _write_state(st)
        return

    _rotate()
    with open(EVENTS, "a") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    _write_state(st)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass                                     # a metrics hook must never fail loudly
    sys.exit(0)

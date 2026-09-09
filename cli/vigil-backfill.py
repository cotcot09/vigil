#!/usr/bin/env python3
"""Seed VIGIL from Claude Code transcripts already on this machine.

Without this the app opens empty and stays empty for a week. With it, the first
launch shows a real dial, which is the whole difference between a tool someone
tries and one they keep.
"""
import os, sys, json, glob, datetime, argparse, hashlib

ROOT   = os.environ.get("VIGIL_HOME", os.path.join(os.path.expanduser("~"), ".vigil"))
EVENTS = os.path.join(ROOT, "events.jsonl")
BIN    = 300


def is_typed_prompt(rec):
    """A message the human actually typed, not a tool result echoed back."""
    if rec.get("type") != "user":
        return False
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, str):
        return bool(c.strip())
    if isinstance(c, list):
        return not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects-dir",
                    default=os.path.join(os.path.expanduser("~"), ".claude", "projects"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    files = glob.glob(os.path.join(a.projects_dir, "*", "*.jsonl"))
    if not files:
        print("No transcripts found.", file=sys.stderr)
        return 1

    bins, prompts, sessions = {}, [], {}
    for f in files:
        project = os.path.basename(os.path.dirname(f)).split("-")[-1] or "unknown"
        with open(f, errors="ignore") as fh:
            for line in fh:
                if '"timestamp"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                ts = rec.get("timestamp")
                if not ts:
                    continue
                try:
                    t = datetime.datetime.fromisoformat(
                        ts.replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
                bins.setdefault(int(t // BIN), project)
                if is_typed_prompt(rec):
                    prompts.append((t, project))
                sid = rec.get("sessionId")
                if sid:
                    sessions[sid] = project

    rows  = [{"t": b * BIN, "k": "tick", "p": p} for b, p in sorted(bins.items())]
    rows += [{"t": round(t, 1), "k": "prompt", "p": p} for t, p in sorted(prompts)]
    rows += [{"t": min(bins) * BIN if bins else 0, "k": "session", "p": p,
              "s": hashlib.sha1(s.encode()).hexdigest()[:12]}
             for s, p in sessions.items()]
    rows.sort(key=lambda r: r["t"])

    print(f"{len(files)} transcripts → {len(bins)} active bins, "
          f"{len(prompts)} prompts, {len(sessions)} sessions")
    if a.dry_run:
        return 0

    os.makedirs(ROOT, exist_ok=True)
    if os.path.exists(EVENTS):
        os.replace(EVENTS, EVENTS + ".before-backfill")
        print(f"existing log moved to {EVENTS}.before-backfill")
    with open(EVENTS, "w") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    print(f"wrote {len(rows)} events → {EVENTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""VIGIL aggregator — reads Claude Code's own transcripts and reports when you work.

Claude Code writes every session to ~/.claude/projects/<project>/<id>.jsonl as it
happens, with a timestamp on every record. That is already the dataset, so this
reads it directly rather than depending on a hook to mirror it. One less moving
part, it works retroactively, and it cannot silently stop recording.

Transcripts are append-only, so parsing is incremental: each file is read from
the byte offset where the last run stopped.
"""
import os, sys, json, glob, datetime, collections, argparse

HOME    = os.path.expanduser("~")
ROOT    = os.environ.get("VIGIL_HOME", os.path.join(HOME, ".vigil"))
INDEX   = os.path.join(ROOT, "index.json")
PROJECTS = os.environ.get("VIGIL_PROJECTS",
                          os.path.join(HOME, ".claude", "projects"))
BIN   = 300
NIGHT = {22, 23, 0, 1, 2, 3, 4, 5}


def _typed_prompt(rec):
    """A message the human actually typed, not a tool result echoed back."""
    if rec.get("type") != "user":
        return False
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, str):
        return bool(c.strip())
    if isinstance(c, list):
        return not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c)
    return False


def _load_index():
    try:
        with open(INDEX) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_index(idx):
    os.makedirs(ROOT, exist_ok=True)
    tmp = INDEX + ".tmp"
    with open(tmp, "w") as f:
        json.dump(idx, f, separators=(",", ":"))
    os.replace(tmp, INDEX)


def scan():
    """Return (bins:set[int], prompts:list[float], sessions:set, projects:Counter)."""
    idx = _load_index()
    files = sorted(glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")))

    bins, prompts, sessions = set(), [], set()
    projects = collections.Counter()

    for path in files:
        try:
            size = os.path.getsize(path)
        except OSError:
            continue

        entry = idx.get(path) or {}
        offset = entry.get("offset", 0)
        # A shrunk file means it was rotated or replaced: start over on it.
        if size < offset:
            entry, offset = {}, 0

        cached_bins = set(entry.get("bins", []))
        cached_prompts = list(entry.get("prompts", []))
        cached_sessions = set(entry.get("sessions", []))
        project = os.path.basename(os.path.dirname(path)).split("-")[-1] or "unknown"

        if size > offset:
            try:
                with open(path, "r", errors="ignore") as fh:
                    fh.seek(offset)
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
                        cached_bins.add(int(t // BIN))
                        if _typed_prompt(rec):
                            cached_prompts.append(round(t, 1))
                        sid = rec.get("sessionId")
                        if sid:
                            cached_sessions.add(sid[:12])
                    offset = fh.tell()
            except OSError:
                continue

        idx[path] = {"offset": offset, "bins": sorted(cached_bins),
                     "prompts": cached_prompts, "sessions": sorted(cached_sessions),
                     "project": project}

        bins |= cached_bins
        prompts += cached_prompts
        sessions |= cached_sessions
        projects[project] += len(cached_prompts) or 1

    _save_index(idx)
    return bins, prompts, sessions, projects


def summarise(since_days=None):
    tz = datetime.datetime.now().astimezone().tzinfo
    bins, prompts, sessions, projects = scan()
    if not bins:
        return None

    cutoff = 0.0
    if since_days:
        cutoff = (datetime.datetime.now(tz)
                  - datetime.timedelta(days=since_days)).timestamp()
        bins = {b for b in bins if b * BIN >= cutoff}
        prompts = [p for p in prompts if p >= cutoff]
    if not bins:
        return None

    hours, days = collections.Counter(), set()
    for b in bins:
        dt = datetime.datetime.fromtimestamp(b * BIN, tz)
        hours[dt.hour] += BIN // 60
        days.add(dt.date())

    minutes = len(bins) * (BIN // 60)
    total   = sum(hours.values()) or 1
    night   = sum(hours.get(h, 0) for h in NIGHT)
    peak    = max(hours, key=lambda h: hours[h])
    stamps  = sorted(b * BIN for b in bins)

    return {
        "minutes": minutes, "hours": minutes // 60, "mins": minutes % 60,
        "prompts": len(prompts), "days": len(days),
        "sessions": len(sessions), "projects": len(projects),
        "peakHour": peak, "nightShare": round(night * 100 / total),
        "byHour": [hours.get(h, 0) for h in range(24)],
        "firstSeen": datetime.datetime.fromtimestamp(stamps[0],  tz).isoformat(),
        "lastSeen":  datetime.datetime.fromtimestamp(stamps[-1], tz).isoformat(),
        "timezone": str(tz),
        "utcOffsetMin": int(datetime.datetime.now(tz).utcoffset().total_seconds() // 60),
        "generatedAt": datetime.datetime.now(tz).isoformat(),
    }


def clock(h):
    return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Summarise VIGIL activity.")
    ap.add_argument("--days", type=int, help="only the last N days")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    s = summarise(a.days)
    if not s:
        print("No Claude Code activity found yet.", file=sys.stderr)
        sys.exit(1)

    if a.json:
        print(json.dumps(s, indent=1))
    else:
        mx = max(s["byHour"]) or 1
        print(f"\n  {s['hours']}h {s['mins']}m logged · {s['prompts']} prompts · "
              f"{s['days']} days · {s['projects']} projects")
        print(f"  Peak {clock(s['peakHour'])} · {s['nightShare']}% between 10 PM and 6 AM\n")
        for h in range(24):
            v = s["byHour"][h]
            print(f"  {clock(h):>5}  {'█' * int(26 * v / mx):<26} {v:>4}m")
        print()

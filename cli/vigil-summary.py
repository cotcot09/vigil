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
PEAK_WINDOW_HOURS = 5   # length of the block we search for, not its position


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

    by_project = collections.defaultdict(
        lambda: {"bins": set(), "prompts": [], "sessions": set(), "cwd": ""})

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
        # The directory name is a path with slashes replaced by hyphens, so a
        # folder that already contains a hyphen cannot be recovered from it.
        # Every record carries the real cwd; use that instead.
        project = entry.get("project") or "unknown"
        cwd = entry.get("cwd") or ""

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
                        if not cwd and rec.get("cwd"):
                            cwd = rec["cwd"]
                            project = os.path.basename(cwd.rstrip("/")) or "unknown"
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
                     "project": project, "cwd": cwd}

        by_project[project]["bins"] |= cached_bins
        by_project[project]["prompts"] += cached_prompts
        by_project[project]["sessions"] |= cached_sessions
        by_project[project]["cwd"] = cwd or by_project[project].get("cwd", "")

    _save_index(idx)
    return by_project


def project_list():
    """Every project seen, newest activity first."""
    out = []
    for name, d in scan().items():
        if not d["bins"]:
            continue
        last = max(d["bins"]) * BIN
        out.append({"project": name, "cwd": d["cwd"],
                    "minutes": len(d["bins"]) * (BIN // 60),
                    "prompts": len(d["prompts"]),
                    "lastActive": last})
    return sorted(out, key=lambda p: p["lastActive"], reverse=True)


def summarise(since_days=None, project=None):
    """`project` scopes to one folder. None means the most recently worked in;
    pass "*" for everything across every project."""
    tz = datetime.datetime.now().astimezone().tzinfo
    per = scan()
    if not per:
        return None

    if project is None:
        project = max(per, key=lambda k: max(per[k]["bins"], default=0))

    if project == "*":
        bins = set().union(*(d["bins"] for d in per.values()))
        prompts = [p for d in per.values() for p in d["prompts"]]
        sessions = set().union(*(d["sessions"] for d in per.values()))
        scope, cwd = "All projects", ""
    else:
        d = per.get(project)
        if not d:
            return None
        bins, prompts, sessions = d["bins"], d["prompts"], d["sessions"]
        scope, cwd = project, d["cwd"]

    projects = per
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
    peak    = max(hours, key=lambda h: hours[h])

    # The single most-worked contiguous block, wherever it actually falls —
    # not assumed to be 10 PM-6 AM. Slides an 8-hour window around the clock
    # (wrapping past midnight) and keeps whichever position covers the most
    # of this person's real hours. Ties keep the earliest start, so the
    # result is stable across otherwise-identical runs.
    best_start, best_sum = 0, -1
    for start in range(24):
        total_in_window = sum(hours.get((start + i) % 24, 0)
                              for i in range(PEAK_WINDOW_HOURS))
        if total_in_window > best_sum:
            best_start, best_sum = start, total_in_window
    peak_end = (best_start + PEAK_WINDOW_HOURS) % 24
    stamps  = sorted(b * BIN for b in bins)

    return {
        "minutes": minutes, "hours": minutes // 60, "mins": minutes % 60,
        "prompts": len(prompts), "days": len(days),
        "sessions": len(sessions), "projects": len(projects),
        "project": scope, "cwd": cwd,
        "peakHour": peak,
        "peakShare": round(best_sum * 100 / total),
        "peakStartHour": best_start, "peakEndHour": peak_end,
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
    ap.add_argument("--project", help='folder name, or "*" for every project')
    ap.add_argument("--list", action="store_true", help="show every project seen")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.list:
        for p in project_list():
            when = datetime.datetime.fromtimestamp(
                p["lastActive"], datetime.datetime.now().astimezone().tzinfo)
            print(f"  {p['project']:<22} {p['minutes']//60:>3}h {p['minutes']%60:02d}m "
                  f"{p['prompts']:>5} prompts   last {when:%d %b %H:%M}")
        sys.exit(0)

    s = summarise(a.days, a.project)
    if not s:
        print("No Claude Code activity found yet.", file=sys.stderr)
        sys.exit(1)

    if a.json:
        print(json.dumps(s, indent=1))
    else:
        mx = max(s["byHour"]) or 1
        print(f"\n  {s['project']} — {s['hours']}h {s['mins']}m · {s['prompts']} prompts · "
              f"{s['days']} days")
        print(f"  Peak {clock(s['peakHour'])} · {s['peakShare']}% between "
              f"{clock(s['peakStartHour'])} and {clock(s['peakEndHour'])}\n")
        for h in range(24):
            v = s["byHour"][h]
            print(f"  {clock(h):>5}  {'█' * int(26 * v / mx):<26} {v:>4}m")
        print()

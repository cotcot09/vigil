#!/usr/bin/env python3
"""VIGIL aggregator — turns the raw event log into the numbers the app renders.

Emits exactly the shape the dial needs and nothing else, so the iOS side never
has to know how collection works.
"""
import os, sys, json, datetime, collections, argparse

ROOT   = os.environ.get("VIGIL_HOME", os.path.join(os.path.expanduser("~"), ".vigil"))
EVENTS = os.path.join(ROOT, "events.jsonl")
BIN    = 300
NIGHT  = {22, 23, 0, 1, 2, 3, 4, 5}          # 10 PM to 6 AM, the hours that count


def load(paths):
    for p in paths:
        try:
            with open(p) as f:
                for line in f:
                    try:
                        yield json.loads(line)
                    except Exception:
                        continue
        except FileNotFoundError:
            continue


def summarise(since_days=None):
    tz    = datetime.datetime.now().astimezone().tzinfo
    rows  = list(load([EVENTS + ".1", EVENTS]))
    if not rows:
        return None

    cutoff = 0.0
    if since_days:
        cutoff = (datetime.datetime.now(tz)
                  - datetime.timedelta(days=since_days)).timestamp()

    bins, prompts, sessions, projects = set(), 0, set(), collections.Counter()
    for r in rows:
        t = r.get("t", 0)
        if t < cutoff:
            continue
        k = r.get("k")
        if k == "tick":
            bins.add(int(t // BIN))
            projects[r.get("p", "unknown")] += 1
        elif k == "prompt":
            prompts += 1
            projects[r.get("p", "unknown")] += 1
        elif k == "session":
            sessions.add(r.get("s", ""))

    if not bins:
        return None

    hours = collections.Counter()
    days  = set()
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
        "minutes":     minutes,
        "hours":       minutes // 60,
        "mins":        minutes % 60,
        "prompts":     prompts,
        "days":        len(days),
        "sessions":    len(sessions),
        "projects":    len(projects),
        "peakHour":    peak,
        "nightShare":  round(night * 100 / total),
        "byHour":      [hours.get(h, 0) for h in range(24)],
        "firstSeen":   datetime.datetime.fromtimestamp(stamps[0],  tz).isoformat(),
        "lastSeen":    datetime.datetime.fromtimestamp(stamps[-1], tz).isoformat(),
        "timezone":    str(tz),
        "utcOffsetMin": int(datetime.datetime.now(tz).utcoffset().total_seconds() // 60),
        "generatedAt": datetime.datetime.now(tz).isoformat(),
    }


def clock(h):
    suffix = "AM" if h < 12 else "PM"
    base   = h % 12 or 12
    return f"{base} {suffix}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Summarise VIGIL activity.")
    ap.add_argument("--days", type=int, help="only the last N days")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()

    s = summarise(a.days)
    if not s:
        print("No activity recorded yet. Install the hooks and use Claude Code.",
              file=sys.stderr)
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
            mark = "█" * int(26 * v / mx)
            print(f"  {clock(h):>5}  {mark:<26} {v:>4}m")
        print()

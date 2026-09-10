#!/usr/bin/env python3
"""Hand the summary to the phone over the local network, and nowhere else.

The Mac advertises itself with Bonjour; the app finds it without anyone typing
an address or a pairing code. Data crosses the room, never the internet — there
is no account, no relay and no cloud storage anywhere in this path.
"""
import os, sys, json, atexit, signal, socket, secrets, argparse, subprocess, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib.machinery import SourceFileLoader

_summary = SourceFileLoader(
    "notte_summary",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "notte-summary.py")
).load_module()

SERVICE = "_notte._tcp"
PORT    = int(os.environ.get("NOTTE_PORT", "7391"))
ROOT    = os.environ.get("NOTTE_HOME", os.path.join(os.path.expanduser("~"), ".notte"))
TOKEN_F = os.path.join(ROOT, "token")

# Unambiguous alphabet: no O/0, I/1, so a code read off a screen and typed
# into a phone cannot be mistyped in the ways people actually mistype.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def pairing_token():
    """Stable per-Mac secret. Created once, reused forever after."""
    try:
        with open(TOKEN_F) as f:
            t = f.read().strip()
            if t:
                return t
    except FileNotFoundError:
        pass
    import secrets
    t = "".join(secrets.choice(ALPHABET) for _ in range(8))
    os.makedirs(ROOT, exist_ok=True)
    with open(TOKEN_F, "w") as f:
        f.write(t)
    os.chmod(TOKEN_F, 0o600)
    return t


TOKEN = pairing_token()


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 1))          # TEST-NET-1: routes nowhere, never sends
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _authorised(self, query):
        supplied = (self.headers.get("X-Notte-Token")
                    or (query.get("token") or [""])[0]).strip().upper()
        # Bytes, not str: compare_digest raises TypeError on non-ASCII, which
        # would turn a mistyped code into a 500 instead of a clean refusal.
        return secrets.compare_digest(supplied.encode("utf-8", "replace"),
                                      TOKEN.encode())

    def do_GET(self):
        import urllib.parse as up
        parts = up.urlparse(self.path)
        path = parts.path.rstrip("/")
        query = up.parse_qs(parts.query)

        # /health stays open so a phone can tell "wrong Mac" apart from
        # "no Mac here", which is the difference between a useful error
        # message and a spinner that never resolves.
        if path != "/health" and not self._authorised(query):
            return self._send(401, json.dumps({"error": "pairing required"}))

        if path in ("/summary", ""):
            # Recomputed per request, so the phone always sees the live number.
            # No project means the one worked in most recently.
            project = (query.get("project") or [None])[0]
            days = (query.get("days") or [None])[0]
            s = _summary.summarise(int(days) if days and days.isdigit() else None,
                                   project)
            if not s:
                return self._send(503, json.dumps(
                    {"error": "no activity found for that project"}))
            return self._send(200, json.dumps(s, separators=(",", ":")))

        if path == "/projects":
            return self._send(200, json.dumps(
                {"projects": _summary.project_list()}, separators=(",", ":")))

        if path == "/health":
            return self._send(200, json.dumps({"ok": True, "service": "notte"}))

        self._send(404, json.dumps({"error": "not found"}))

    def log_message(self, *_):
        pass                                   # the terminal shows status, not a request log


def advertise(port, name):
    """Register with Bonjour using the dns-sd binary macOS already ships.

    Clears any previous advertiser first. If this process is killed without
    running its handlers, the child survives and keeps announcing a service
    that no longer answers — and a phone that finds a dead record can stall
    on it. launchd restarting us would otherwise stack advertisers too.
    """
    subprocess.run(["pkill", "-f", f"dns-sd -R .* {SERVICE}"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        child = subprocess.Popen(
            ["dns-sd", "-R", name, SERVICE, "local", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return None
    atexit.register(lambda: child.terminate())
    return child


def main():
    ap = argparse.ArgumentParser(description="Serve the NOTTE summary to your phone.")
    ap.add_argument("--port", type=int, default=PORT)
    a = ap.parse_args()

    # Deliberately does not refuse to start on an empty history. The agent
    # runs under launchd with KeepAlive, so exiting here was a crash loop,
    # and a phone got "no Mac found" when the truthful answer was "your Mac
    # is fine, it just has nothing to report yet" — which /summary says with
    # a 503 as soon as anyone asks.
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", a.port), Handler)
    except OSError as e:
        print(f"Could not listen on port {a.port}: {e}", file=sys.stderr)
        print("Something else is using it. Pick another with:", file=sys.stderr)
        print(f"    NOTTE_PORT=7392 {sys.argv[0]}", file=sys.stderr)
        print("and enter the address with that port in the app.", file=sys.stderr)
        return 1
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    bonjour = advertise(a.port, socket.gethostname().replace(".local", ""))

    ip = lan_ip()
    print()
    print("  NOTTE is ready. Open the app on your phone and enter this code:")
    print()
    print(f"      {TOKEN[:4]} - {TOKEN[4:]}")
    print()
    print(f"    discoverable as   {SERVICE} on this network")
    print(f"    if it cannot be found, type this into the app instead:")
    print(f"                      {ip}:{a.port}")
    print()
    print("  The code pairs this Mac to your phone, so a shared network cannot")
    print("  read your hours and your phone cannot latch onto someone else's Mac.")
    print()

    def stop(*_):
        if bonjour:
            bonjour.terminate()
        srv.shutdown()
        print("\n  Stopped.\n")
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    signal.pause()


if __name__ == "__main__":
    sys.exit(main())

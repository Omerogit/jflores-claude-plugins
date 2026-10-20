"""Setup-JFlores.cmd, run whole on a real Windows machine against a stand-in steward room, in a scratch profile.
    python setup/test_setup_windows.py ok|upgrade|settings|nogit|noconn
ok: a fresh profile. upgrade: Omar's 10-19 laptop (a zip-folder marketplace, steward 1.1.0). settings: an existing
settings.json must be kept. nogit: Git can't be installed, so the steward works and the setup says what's left.
noconn (MUST FAIL): no connection file, so it stops at step 5. It uses the real Claude Code on this machine with
CLAUDE_CONFIG_DIR pointed at the scratch profile; the profile lives under %LOCALAPPDATA%\Temp\jft, because git
can't write deeper paths ("Filename too long"). Proved 2026-10-19 on Omero's bench: all five as described."""
import json, os, shutil, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
ROOM = []
class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.headers.get("authorization") != "Bearer tok_test": return self._send(401, {"error": "no"})
        since = float(parse_qs(urlparse(self.path).query).get("since", ["0"])[0])
        lines = [m for m in ROOM if m["ts"] > since]
        return self._send(200, {"lines": lines, "total_new": len(lines), "newest": ROOM[-1]["ts"] if ROOM else since})
    def do_POST(self):
        if self.headers.get("authorization") != "Bearer tok_test": return self._send(401, {"error": "no"})
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        out = []
        for p in body.get("posts") or []:
            mid = "m%d" % (len(ROOM) + 1)
            ROOM.append({"id": mid, "ts": time.time(), "author_id": "omar", "kind": "bench", "body": p["text"]})
            out.append({"id": p.get("id"), "ok": True, "mid": mid})
        return self._send(200, {"posted": out})
srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = os.path.join(os.environ["LOCALAPPDATA"], "Temp", "jft")
shutil.rmtree(base, ignore_errors=True)
home = os.path.join(base, "home user")          # a space, like "Omar Samuel"
cfg = os.path.join(home, ".claude")
os.makedirs(os.path.join(cfg, "steward"))
mode = sys.argv[1] if len(sys.argv) > 1 else "ok"
if mode != "noconn":
    json.dump({"base": "http://127.0.0.1:%d" % srv.server_port, "token": "tok_test", "person": "omar",
               "steward": "omar-samuel"}, open(os.path.join(cfg, "steward", "thread.json"), "w"))
env = dict(os.environ, JF_TEST_HOME=home, CLAUDE_CONFIG_DIR=cfg, USERPROFILE=home, HOME=home)
if mode == "settings":
    json.dump({"permissions": {"allow": ["Bash(ls:*)"]}, "env": {"X": "1"}}, open(os.path.join(cfg, "settings.json"), "w"))
if mode == "nogit":
    env["JF_TEST_NOGIT"] = "1"
if mode == "upgrade":       # Omar's laptop: a zip-folder marketplace from 10-02/10-18, steward 1.1.0 installed
    import urllib.request, zipfile, io
    z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen("https://codeload.github.com/Omerogit/jflores-claude-plugins/zip/05b1c58").read()))
    z.extractall(base); inner = [d for d in os.listdir(base) if d.startswith("jflores")][0]
    md = os.path.join(home, ".claude", "jflores-plugins"); shutil.move(os.path.join(base, inner), md)
    cl = shutil.which("claude")
    for a in (["plugin", "marketplace", "add", md], ["plugin", "install", "steward@jflores", "-s", "user"], ["plugin", "install", "refocus@jflores", "-s", "user"]):
        subprocess.run([cl] + a, env=env, capture_output=True, timeout=180)
    print("BEFORE:", os.listdir(os.path.join(cfg, "plugins", "cache", "jflores", "steward")))
r = subprocess.run(["cmd.exe", "/c", os.path.join(os.path.dirname(os.path.abspath(__file__)), "Setup-JFlores.cmd")], stdin=subprocess.DEVNULL, env=env,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
print(r.stdout[-3000:]); print("STDERR:", r.stderr[-800:])
print("ROOM got %d line(s):" % len(ROOM), [m["body"][:140] for m in ROOM])

kp = os.path.join(cfg, "plugins", "known_marketplaces.json")
if os.path.exists(kp):
    print("MARKETPLACE:", json.load(open(kp)).get("jflores", {}).get("source"))
sp = os.path.join(cfg, "settings.json")
if os.path.exists(sp):
    print("SETTINGS:", " ".join(open(sp).read().split())[:400])

"""The share rail's plugin side (share.py + the watch's share_answers), tested against a stub door on localhost.
    python tests/test_share.py
Offline on purpose: a share to the real door calls Monday's seat. The door's own side is tested in
brain_door/test_door.py; the whole loop was proven live once, 2026-10-02 (help-zztest, Monday answered in a minute)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARE = os.path.join(ROOT, "plugins", "refocus", "skills", "share", "scripts", "share.py")
WATCH = os.path.join(ROOT, "plugins", "refocus", "scripts", "watch.py")
fails = []
ROOM = {"msgs": [], "posts": []}


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:600]), flush=True)
    if not cond:
        fails.append(name)


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if self.headers.get("Authorization") != "Bearer bd_test":
            return self._send(401, {"error": "a Brain key is required"})
        since = float(parse_qs(u.query).get("since", ["0"])[0])
        msgs = [m for m in ROOM["msgs"] if m["ts"] > since and (u.path == "/v1/share" or not m["mine"])]
        return self._send(200, {"room": "help-zztest", "messages": msgs})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        ROOM["posts"].append(body)
        m = {"id": "m%d" % len(ROOM["msgs"]), "from": "Zztest's Claude Code", "ts": time.time(), "body": body["text"],
             "mine": True, "reply_to": None}
        ROOM["msgs"].append(m)
        return self._send(200, {"verified": True, "verify": "PASS", "id": m["id"], "room": "help-zztest",
                                "called": "monday"})


srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=srv.serve_forever, daemon=True).start()
DOOR = "http://127.0.0.1:%d" % srv.server_address[1]
tmp = tempfile.mkdtemp(prefix="share-")
RH = os.path.join(tmp, "refocus")
ENV = dict(os.environ, REFOCUS_HOME=RH, PYTHONIOENCODING="utf-8", REFOCUS_IGNORE_HOUSE_WATCH="1",
           REFOCUS_SHARE_EVERY="0")
ENV.pop("OFFICE_SEAT", None)


def share(*args):
    r = subprocess.run([sys.executable, SHARE] + list(args), env=ENV, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout + r.stderr


def watch():
    time.sleep(2.1)                  # the double-install guard: one look per 2 s
    ev = json.dumps({"session_id": "t", "transcript_path": ""})
    r = subprocess.run([sys.executable, WATCH], input=ev, env=ENV, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout


try:
    rc, out = share("send", "--text", "hello")
    check("no brain connected: nothing sent, says so (exit 3)", rc == 3 and "NO BRAIN" in out and not ROOM["posts"], out)
    rc, out = watch()
    check("the watch is silent when nothing was ever shared", rc == 0 and out == "", out)
    os.makedirs(RH)
    with open(os.path.join(RH, "door.json"), "w", encoding="utf-8") as f:
        json.dump({"door": DOOR, "key": "bd_test", "partner": "zz-doortest"}, f)
    rc, out = watch()
    check("connected but nothing shared: the watch does not even ask the door", rc == 0 and out == "", out)
    old = time.time() - 5
    ROOM["msgs"].append({"id": "old", "from": "Monday", "ts": old, "body": "an answer from before", "mine": False,
                         "reply_to": None})
    fn = os.path.join(tmp, "t.txt")
    with open(fn, "w", encoding="utf-8") as f:
        f.write("claude is not recognized\n")
    rc, out = share("send", "--title", "PATH", "--file", fn)
    check("send: SENT, VERIFY PASS, says Monday was called", rc == 0 and "VERIFY PASS" in out and "Monday was called"
          in out and ROOM["posts"][-1] == {"title": "PATH", "text": "claude is not recognized\n"}, out)
    rc, out = share("replies")
    check("an answer from before the first share is not new", rc == 0 and "No answer yet" in out, out)
    rc, out = watch()
    check("its own share never comes back as an answer", rc == 0 and out == "", out)
    ROOM["msgs"].append({"id": "a1", "from": "Monday", "ts": time.time() + 0.0000004, "body": "Use the PowerShell line.",
                         "mine": False, "reply_to": "m1"})
    rc, out = watch()
    check("the next prompt after an answer hands it to the session, to show the person first",
          rc == 0 and "SHARE RAIL" in out and "Show it to them first" in out and "Use the PowerShell line." in out
          and "from Monday" in out and "an answer from before" not in out, out)
    rc, out = watch()
    check("an answer is handed over once (exact timestamps, no float rounding)", rc == 0 and out == "", out)
    rc, out = share("replies")
    check("replies shows nothing new after the watch showed it", "No answer yet" in out, out)
    rc, out = share("replies", "--all")
    check("replies --all shows every answer", "Use the PowerShell line." in out and "an answer from before" in out, out)
    rc, out = share("thread")
    check("thread shows both sides, this computer named as such", "from this computer" in out and "from Monday" in out, out)
    with open(os.path.join(RH, "share.json"), encoding="utf-8") as f:
        st = json.load(f)
    st["last_share"] = time.time() - 15 * 86400
    with open(os.path.join(RH, "share.json"), "w", encoding="utf-8") as f:
        json.dump(st, f)
    ROOM["msgs"].append({"id": "a2", "from": "Omero", "ts": time.time(), "body": "late", "mine": False, "reply_to": None})
    rc, out = watch()
    check("two weeks after the last share the watch stops looking", rc == 0 and out == "", out)
    st["last_share"] = time.time()
    with open(os.path.join(RH, "share.json"), "w", encoding="utf-8") as f:
        json.dump(st, f)
    srv.shutdown()
    srv.server_close()
    t0 = time.time()
    rc, out = watch()
    check("door down: the watch stays silent and quick", rc == 0 and out == "" and time.time() - t0 < 10, (out, time.time() - t0))
    rc, out = share("send", "--text", "x")
    check("door down: send says nothing was sent (exit 6)", rc == 6 and "Nothing was sent" in out, out)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n%d FAILED" % len(fails) if fails else "\nALL PASS")
sys.exit(1 if fails else 0)

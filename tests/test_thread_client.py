# -*- coding: utf-8 -*-
"""The laptop half of a steward's one thread (w-d722be54), tested against a stub door on localhost - never the
live steward_door.py. The door's own side (the claim-link mint/take/peek and the /thread ledger) is tested in
the build that owns it (test_steward_door_unit.py, run as uid steward-samuel); this file is offline, Hiram's own
half of the labor split, and proves only the laptop's two pieces: steward.py's new `thread-connect` command, and
thread_client.py's hook integration (hook.py's UserPromptSubmit/Stop paths, driven exactly as Claude Code drives
them - JSON on stdin, text on stdout).
    python tests/test_thread_client.py
"""
import importlib.util as ilu
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
ST = os.path.join(ROOT, "plugins", "steward")
STEWARD = os.path.join(ST, "skills", "start", "scripts", "steward.py")
HOOK = os.path.join(ST, "scripts", "hook.py")
fails = []
ROOM = {"msgs": []}             # {"id","ts","author_id","name","kind","body"}
LEDGER = {}


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
        if self.headers.get("authorization") != "Bearer tok_test":
            return self._send(401, {"error": "no"})
        since = float(parse_qs(u.query).get("since", ["0"])[0])
        lines = [dict(m) for m in ROOM["msgs"] if m["ts"] > since]
        return self._send(200, {"lines": lines, "total_new": len(ROOM["msgs"]),
                                "newest": ROOM["msgs"][-1]["ts"] if ROOM["msgs"] else since})

    def do_POST(self):
        if self.headers.get("authorization") != "Bearer tok_test":
            return self._send(401, {"error": "no"})
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        out = []
        for p in body.get("posts") or []:
            cid = p.get("id")
            if cid in LEDGER:
                out.append({"id": cid, "ok": True, "mid": LEDGER[cid], "again": True})
                continue
            who = {"person": "omar", "steward": "omar-samuel"}.get(p.get("who"))
            if not who or not str(p.get("text") or "").strip():
                out.append({"id": cid, "ok": False, "error": "refused"})
                continue
            mid = "m%d" % (len(ROOM["msgs"]) + 1)
            name = "Omar" if who == "omar" else "Samuel"
            ROOM["msgs"].append({"id": mid, "ts": time.time(), "author_id": who, "name": name, "kind": "bench",
                                 "body": p["text"]})
            LEDGER[cid] = mid
            out.append({"id": cid, "ok": True, "mid": mid})
        return self._send(200, {"posted": out})


srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d" % srv.server_address[1]
tmp = tempfile.mkdtemp(prefix="thread-client-")
SH = os.path.join(tmp, "steward")
ENV = dict(os.environ, STEWARD_HOME=SH, STEWARD_IGNORE_HOUSE="1", PYTHONIOENCODING="utf-8")
ENV.pop("OFFICE_SEAT", None)
THREAD_CONF = os.path.join(SH, "thread.json")


def hook(event_name, **fields):
    ev = {"hook_event_name": event_name}
    ev.update(fields)
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(ev), env=ENV, capture_output=True, text=True,
                       timeout=60)
    return r.returncode, r.stdout + r.stderr


def steward(*args):
    r = subprocess.run([sys.executable, STEWARD] + list(args), env=ENV, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout + r.stderr


# ── steward.py's new thread-connect command, exercised in-process (CLAIM_RX requires https://, the stub is http)
def test_thread_connect():
    sp = ilu.spec_from_file_location("steward_under_test", STEWARD)
    m = ilu.module_from_spec(sp)
    sp.loader.exec_module(m)
    m.SD = SH
    m.THREAD_CONF = THREAD_CONF
    m.http = lambda method, url, key=None, body=None, timeout=60: (
        200, {"token": "tok_test", "base": BASE, "person": "omar", "steward": "omar-samuel", "person_name": "Omar"})
    import argparse
    m.cmd_thread_connect(argparse.Namespace(link="https://door.example/steward/samuel/claim/abc12345678901234567890"))
    check("thread-connect writes thread.json with the claimed token and base", os.path.exists(THREAD_CONF))
    with open(THREAD_CONF, encoding="utf-8") as f:
        c = json.load(f)
    check("thread.json carries token/base/person/steward/person_name",
         (c.get("token"), c.get("base"), c.get("person"), c.get("steward"), c.get("person_name")) ==
         ("tok_test", BASE, "omar", "omar-samuel", "Omar"), c)


def transcript(prompt, reply):
    """A minimal transcript.jsonl shaped like Claude Code's own, just enough for hook.py's
    last_assistant_text() to find the reply after the last real user prompt."""
    path = os.path.join(tmp, "transcript-%d.jsonl" % len(ROOM["msgs"]))
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "isSidechain": False,
                            "message": {"content": prompt}}) + "\n")
        f.write(json.dumps({"type": "assistant", "isSidechain": False,
                            "message": {"content": [{"type": "text", "text": reply}]}}) + "\n")
    return path


def write_thread_conf():
    os.makedirs(SH, exist_ok=True)
    with open(THREAD_CONF, "w", encoding="utf-8") as f:
        json.dump({"base": BASE, "token": "tok_test", "person": "omar", "steward": "omar-samuel",
                   "person_name": "Omar"}, f)


try:
    test_thread_connect()
    shutil.rmtree(SH, ignore_errors=True)         # the in-process test above left its own thread.json; start clean

    # ── MUST FAIL FIRST: no thread.json at all, nothing the laptop half does should show
    rc, out = hook("UserPromptSubmit", session_id="a1b2c3d4-0000-0000-0000-000000000000", prompt="hello")
    check("no thread.json: the laptop half is a silent no-op (and never blocks the prompt)",
         rc == 0 and "ONE THREAD" not in out, out)
    check("no thread.json: nothing is queued on disk either", not os.path.isdir(os.path.join(SH, "thread")))

    write_thread_conf()

    # ── a person's first prompt posts, and the first read finds an empty room
    rc, out = hook("UserPromptSubmit", session_id="a1b2c3d4-0000-0000-0000-000000000000", prompt="hello from the laptop")
    check("first prompt: no crash, and the line it just posted is not echoed straight back to itself",
         rc == 0 and "ONE THREAD" not in out, out)
    check("first prompt: posted to the stub as who=person", len(ROOM["msgs"]) == 1 and
         ROOM["msgs"][0]["author_id"] == "omar" and "hello from the laptop" in ROOM["msgs"][0]["body"], ROOM["msgs"])

    # ── the steward's Telegram side adds a line; the laptop's NEXT prompt must show it
    ROOM["msgs"].append({"id": "tg1", "ts": time.time(), "author_id": "omar-samuel", "name": "Samuel", "kind": "say",
                         "body": "Reading this from Telegram."})
    rc, out = hook("UserPromptSubmit", session_id="a1b2c3d4-0000-0000-0000-000000000000", prompt="and now a second one")
    check("second prompt: the Telegram-side line comes back as context",
         rc == 0 and "ONE THREAD" in out and "Reading this from Telegram." in out and "Samuel" in out, out)
    check("second prompt: the laptop's OWN first line is not echoed back to itself",
         out.count("hello from the laptop") == 0, out)

    # ── a tool-echo prompt (leading '<') is never synced, so the reply after it is never queued either
    n_before = len(ROOM["msgs"])
    rc, out = hook("UserPromptSubmit", session_id="a1b2c3d4-0000-0000-0000-000000000000", prompt="<command-name>whatever</command-name>")
    check("a tool-echo prompt posts nothing new", len(ROOM["msgs"]) == n_before, (n_before, ROOM["msgs"]))
    tp = transcript("<command-name>whatever</command-name>", "should never be sent")
    rc, out = hook("Stop", session_id="a1b2c3d4-0000-0000-0000-000000000000", transcript_path=tp)
    time.sleep(0.6)
    check("Stop after an unsynced prompt queues nothing (no 'open' turn to answer)",
         len(ROOM["msgs"]) == n_before and "should never be sent" not in json.dumps(ROOM["msgs"]), ROOM["msgs"])

    # ── an ordinary turn: prompt, then Stop carries the reply over in the background
    rc, out = hook("UserPromptSubmit", session_id="a1b2c3d4-0000-0000-0000-000000000000", prompt="what should I do next")
    n_before = len(ROOM["msgs"])
    tp = transcript("what should I do next", "Here is Samuel's reply, typed on the laptop.")
    rc, out = hook("Stop", session_id="a1b2c3d4-0000-0000-0000-000000000000", transcript_path=tp)
    check("Stop itself returns at once (the flush is a detached background process)", rc == 0)
    ok = False
    for _ in range(20):
        if len(ROOM["msgs"]) > n_before:
            ok = True
            break
        time.sleep(0.25)
    check("the background flush posts the laptop's reply as who=steward",
         ok and ROOM["msgs"][-1]["author_id"] == "omar-samuel" and
         "Here is Samuel's reply, typed on the laptop." in ROOM["msgs"][-1]["body"], ROOM["msgs"])

    # ── STEWARD_THREAD=off is the emergency kill switch
    ENV["STEWARD_THREAD"] = "off"
    n_before = len(ROOM["msgs"])
    rc, out = hook("UserPromptSubmit", session_id="a1b2c3d4-0000-0000-0000-000000000000", prompt="this must not be posted")
    check("STEWARD_THREAD=off: a silent no-op even with thread.json present",
         rc == 0 and "ONE THREAD" not in out and len(ROOM["msgs"]) == n_before, out)
    del ENV["STEWARD_THREAD"]

    # ── the door being unreachable never blocks the prompt, and names what happened
    srv.shutdown()
    srv.server_close()
    t0 = time.time()
    rc, out = hook("UserPromptSubmit", session_id="a1b2c3d4-0000-0000-0000-000000000000", prompt="door is down now")
    check("door down: the prompt still goes through, quickly, with one plain note",
         rc == 0 and time.time() - t0 < 10 and "[steward]" in out, (out, time.time() - t0))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n%d FAILED" % len(fails) if fails else "\nALL PASS")
sys.exit(1 if fails else 0)

# -*- coding: utf-8 -*-
# Steward 1.1.12 (2026-11-21): `steward.py board` reads the person's own open board from the Brain door (GET /v1/board),
# read only. Offline: a local stub door on 127.0.0.1, nothing reaches the server. Covers the populated board, a person
# with no board (Nathan's review: no check bit on that branch), and that no write verb exists.
# Run: python tests/test_steward_board.py   (exit 0 = all pass)
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.join(HERE, "..", "plugins", "steward", "skills", "start", "scripts", "steward.py")
FAILS = []
SEEN = []
ANSWER = {}


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + detail))
    if not cond:
        FAILS.append(name)


class Door(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body):
        d = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(d)))
        self.end_headers()
        self.wfile.write(d)

    def do_GET(self):
        SEEN.append(("GET", self.path, self.headers.get("Authorization")))
        if self.path == "/v1/board" and self.headers.get("Authorization") == "Bearer k-test":
            self._send(200, ANSWER["b"])
        else:
            self._send(404, {"error": "no such door here"})

    def do_POST(self):
        SEEN.append(("POST", self.path, None))
        self._send(404, {"error": "no such door here"})


def run(home, *args):
    env = dict(os.environ, HOME=home, STEWARD_HOME=os.path.join(home, ".claude", "steward"),
               REFOCUS_HOME=os.path.join(home, ".claude", "refocus"), STEWARD_IGNORE_HOUSE="1")
    env.pop("OFFICE_SEAT", None)
    return subprocess.run([sys.executable, SP] + list(args), env=env, capture_output=True, text=True, timeout=60)


def main():
    srv = HTTPServer(("127.0.0.1", 0), Door)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    home = tempfile.mkdtemp(prefix="steward-board-")
    os.makedirs(os.path.join(home, ".claude", "refocus"))
    with open(os.path.join(home, ".claude", "refocus", "door.json"), "w") as f:
        json.dump({"door": "http://127.0.0.1:%d" % srv.server_port, "key": "k-test"}, f)

    ANSWER["b"] = {"ok": True, "person": "haru", "board": True, "count": 2, "cases": [
        {"case": "C-9", "age": "2d", "asked_by": "monday", "ask": "Send Laura M. the warranty form", "job": "14085"},
        {"case": "C-11", "age": "3h", "asked_by": "zen", "ask": "Confirm the part"}]}
    r = run(home, "board")
    check("a board prints its count and says read only", r.returncode == 0 and "Haru: 2 open (read only)" in r.stdout,
          r.stdout + r.stderr)
    check("each case prints number, age, who asked, the ask and the job",
          "C-9 · 2d · asked by monday · Send Laura M. the warranty form · #14085" in r.stdout, r.stdout)
    check("a case with no job prints no job mark", "C-11 · 3h · asked by zen · Confirm the part\n" in r.stdout,
          r.stdout)
    check("it asked the door GET /v1/board with this machine's key and nothing else",
          SEEN == [("GET", "/v1/board", "Bearer k-test")], repr(SEEN))

    del SEEN[:]
    ANSWER["b"] = {"ok": True, "person": "haru", "board": False, "cases": []}
    r = run(home, "board")
    check("a person with no board is told so, plainly, and it exits 0",
          r.returncode == 0 and "Haru has no board on the server." in r.stdout, r.stdout + r.stderr)
    check("no board prints no count line", "open (read only)" not in r.stdout, r.stdout)

    del SEEN[:]
    for verb in ("close", "answer", "pass"):
        r = run(home, verb, "C-9")
        check("there is no `%s` command" % verb, r.returncode != 0 and "invalid choice" in r.stderr, r.stderr[-200:])
    check("and nothing was sent to the door for them", SEEN == [], repr(SEEN))
    srv.shutdown()
    print("\nALL PASS" if not FAILS else "\nFAIL: %d failed" % len(FAILS))
    sys.exit(1 if FAILS else 0)


main()

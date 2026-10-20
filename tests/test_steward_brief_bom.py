# -*- coding: utf-8 -*-
"""steward.py brief, offline against a stub door (never the live Brain): PowerShell pipes stdin with a leading
UTF-8 BOM, and on Omar's machine the whole name-slot answer ("Samuel. He named his steward himself, why not")
rode along as if it were the agent's name. Proves both fixes: text_arg() strips the BOM, and the name slot keeps
only the name - the words before the first sentence break.
    python tests/test_steward_brief_bom.py
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEWARD = os.path.join(ROOT, "plugins", "steward", "skills", "start", "scripts", "steward.py")
fails = []
RECEIVED = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:400]), flush=True)
    if not cond:
        fails.append(name)


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        RECEIVED.append(body)
        b = json.dumps({"anatomy": {"empty": []}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d" % srv.server_address[1]

tmp = tempfile.mkdtemp(prefix="steward-brief-bom-")
RD = os.path.join(tmp, "refocus")
os.makedirs(RD)
with open(os.path.join(RD, "door.json"), "w", encoding="utf-8") as f:
    json.dump({"door": BASE, "key": "tok_test", "partner": "omar-desk"}, f)
ENV = dict(os.environ, REFOCUS_HOME=RD, STEWARD_HOME=os.path.join(tmp, "steward"), STEWARD_IGNORE_HOUSE="1",
          PYTHONIOENCODING="utf-8")
ENV.pop("OFFICE_SEAT", None)

BOM_ANSWER = "﻿Samuel. He named his steward himself, why not".encode("utf-8")


def brief(*args, stdin=None):
    r = subprocess.run([sys.executable, STEWARD, "brief"] + list(args), input=stdin, env=ENV,
                       capture_output=True, timeout=30)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")

# ---------------------------------------------------------------- the real incident, replayed
RECEIVED.clear()
rc, out = brief("name", "--turns", "9", "-", stdin=BOM_ANSWER)
check("brief exits clean", rc == 0, out)
check("the door never sees a BOM character", RECEIVED and "﻿" not in RECEIVED[-1]["text"], RECEIVED)
check("the name slot keeps only the name, not the whole sentence that answered it",
      RECEIVED and RECEIVED[-1]["text"] == "Samuel",
      RECEIVED[-1]["text"] if RECEIVED else None)

# ---------------------------------------------------------------- a plain one-word answer still works
RECEIVED.clear()
rc, out = brief("name", "--turns", "1", "--text", "Samuel")
check("a plain name answer is unchanged", RECEIVED and RECEIVED[-1]["text"] == "Samuel", RECEIVED)

# ---------------------------------------------------------------- a BOM on an ordinary slot is still stripped,
# and the sentence is kept whole - only the name slot is trimmed to one name
RECEIVED.clear()
rc, out = brief("stuck", "--turns", "2", "-", stdin="﻿Starts at 7. Runs long.".encode("utf-8"))
check("an ordinary slot's BOM is stripped but its full answer rides along",
      RECEIVED and RECEIVED[-1]["text"] == "Starts at 7. Runs long.", RECEIVED)

print("\n%d FAILED" % len(fails) if fails else "\nALL PASS")
sys.exit(1 if fails else 0)

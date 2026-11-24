# -*- coding: utf-8 -*-
"""steward 1.1.23: every call to the steward's door names the plugin copy making it (User-Agent: steward-plugin/<version>).

The door keeps a record of each laptop poll (steward-runner-poll-1124) and could not say which plugin was polling, because
1.1.22 sent urllib's default. Offline: a stub on 127.0.0.1 that records the header. MUST FAIL on 1.1.22.
    python tests/test_steward_ua_version.py"""
import importlib.util as ilu
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(ROOT, "plugins", "steward")
fails, SEEN = [], []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:400]), flush=True)
    if not cond:
        fails.append(name)


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _go(self):
        SEEN.append((self.command, self.headers.get("User-Agent"), self.headers.get("Authorization")))
        n = int(self.headers.get("content-length") or "0")
        self.rfile.read(n)
        raw = json.dumps({"lines": [], "posted": []}).encode()
        self.send_response(200)
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    do_GET = do_POST = _go


def load():
    spec = ilu.spec_from_file_location("thread_client_ua", os.path.join(ST, "scripts", "thread_client.py"))
    m = ilu.module_from_spec(spec)
    sys.path.insert(0, os.path.join(ST, "scripts"))
    spec.loader.exec_module(m)
    return m


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    TC = load()
    ver = json.load(open(os.path.join(ST, ".claude-plugin", "plugin.json")))["version"]
    TC.HTTP = None
    code, _ = TC._http("GET", base + "/thread?since=0&full=1", "tok")
    code2, _ = TC._http("POST", base + "/thread", "tok", {"posts": []})
    check("GET and POST reach the stub", code == 200 and code2 == 200, (code, code2))
    check("every call says steward-plugin/<plugin.json version>",
          len(SEEN) == 2 and all(ua == "steward-plugin/" + ver for _, ua, _ in SEEN), SEEN)
    check("the version is a plain x.y.z the door will read", re.match(r"^steward-plugin/[0-9]+\.[0-9]+\.[0-9]+$", (SEEN or [(0, "", 0)])[0][1] or ""), SEEN)
    check("the constant is held to plugin.json", getattr(TC, "PLUGIN_VERSION", None) == ver, (getattr(TC, "PLUGIN_VERSION", None), ver))
    check("the token still goes as a bearer, and only there", all(a == "Bearer tok" for _, _, a in SEEN), SEEN)
    check("the token is not in the User-Agent", all("tok" not in (ua or "") for _, ua, _ in SEEN), SEEN)
    srv.shutdown()
    print("ALL PASS" if not fails else "FAILED: %s" % fails)
    sys.exit(1 if fails else 0)

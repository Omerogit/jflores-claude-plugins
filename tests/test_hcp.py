"""The housecall-pro skill's hcp.py, tested against a stub door on localhost (never the real Housecall Pro).
    python tests/test_hcp.py
The server side (the door's /v1/hcp and hcp-desk-reader) is tested on the server: brain_door/test_door.py and
/opt/hcpdesk/test_reader.py."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HCP = os.path.join(ROOT, "plugins", "refocus", "skills", "housecall-pro", "scripts", "hcp.py")
SKILL = os.path.join(ROOT, "plugins", "refocus", "skills", "housecall-pro", "SKILL.md")
fails = []
SEEN = []
MODE = {"code": 200}


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:600]), flush=True)
    if not cond:
        fails.append(name)


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append({"path": self.path, "auth": self.headers.get("Authorization"), "req": req})
        if MODE["code"] != 200:
            code, out = MODE["code"], {"ok": False, "error": MODE.get("error", "no")}
        elif req["path"] == "/pro/grid/jobs_for_grid":
            code, out = 200, {"ok": True, "status": 200, "data": {"results": [{"uuid": "job_abc", "id": 7}], "total": 1}}
        elif req["path"] == "/jobs/job_abc":
            code, out = 200, {"ok": True, "status": 200, "data": {"id": "job_abc", "invoice_number": "12109"}}
        elif req["path"] == "/alpha/jobs/job_abc/line_items":
            code, out = 200, {"ok": True, "status": 200, "data": {"data": [
                {"name": "Board", "kind": "materials", "quantity": 1,
                 "material_detail": {"data": {"part_number": "WR55X43866"}}}]}}
        elif req["path"] == "/jobs" and ["customer_id", "cus_1"] in req["params"]:
            code, out = 200, {"ok": True, "status": 200, "data": {"jobs": [{"id": "job_abc", "invoice_number": "12109"}],
                                                                   "total_pages": 1}}
        elif req["path"] == "/jobs":
            code, out = 200, {"ok": True, "status": 200, "data": {"total_pages": 1, "jobs": [
                {"id": "j2", "schedule": {"scheduled_start": "2026-10-03T15:00:00Z"}},
                {"id": "j1", "schedule": {"scheduled_start": "2026-10-03T13:00:00Z"}}]}}
        elif req["path"] == "/jobs/job_abc/invoices":
            code, out = 200, {"ok": True, "status": 200, "data": {"invoices": [{"id": "inv_1", "amount": 100}]}}
        elif req["path"] == "/alpha/big":
            code, out = 200, {"ok": True, "status": 200, "data": {"x": "y" * 70000}}
        else:
            code, out = 200, {"ok": True, "status": 200, "data": {"data": [{"id": "cus_1", "display_name": "Zen Test",
                                                                            "mobile_number": "9565551234"}],
                                                                   "total_count": 1}}
        b = json.dumps(out).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=srv.serve_forever, daemon=True).start()
tmp = tempfile.mkdtemp(prefix="hcp-")
try:
    RH = os.path.join(tmp, "refocus")
    env = dict(os.environ, REFOCUS_HOME=RH, PYTHONIOENCODING="utf-8")

    def run(*args):
        r = subprocess.run([sys.executable, HCP] + list(args), env=env, capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout

    rc, out = run("customers", "Garza")
    check("not connected: says so plainly, exit 3, nothing sent", rc == 3 and "NO BRAIN CONNECTED" in out and not SEEN, out)
    os.makedirs(RH)
    json.dump({"door": "http://127.0.0.1:%d" % srv.server_address[1], "key": "bd_test", "partner": "zz-desk"},
              open(os.path.join(RH, "door.json"), "w"))
    rc, out = run("customers", "+1 (956) 555-1234")
    s = SEEN[-1]
    check("a customer search goes to the door's /v1/hcp with this desk's key", rc == 0 and s["path"] == "/v1/hcp"
          and s["auth"] == "Bearer bd_test" and s["req"]["door"] == "web" and s["req"]["path"] == "/alpha/customers", s)
    check("a phone is searched by its bare 10 digits", ["q", "9565551234"] in s["req"]["params"], s["req"])
    check("the answer is printed as customers found", '"found": 1' in out and "Zen Test" in out, out)
    n0 = len(SEEN)
    rc, out = run("job", "#12109")
    paths = [x["req"]["path"] for x in SEEN[n0:]]
    check("a job number is found through the grid (display_invoice_number), then read with its line items",
          rc == 0 and paths == ["/pro/grid/jobs_for_grid", "/jobs/job_abc", "/alpha/jobs/job_abc/line_items"] and
          SEEN[n0]["req"]["method"] == "POST" and
          SEEN[n0]["req"]["body"]["filter"]["filters"][0] == {"field": "display_invoice_number", "operator": "eq",
                                                             "value": "12109"}, (paths, SEEN[n0:]))
    check("the line items show the typed part number", '"part_number": "WR55X43866"' in out, out)
    n0 = len(SEEN)
    rc, out = run("invoices", "--customer", "cus_1")
    paths = [x["req"]["path"] for x in SEEN[n0:]]
    check("invoices for a customer go through its jobs (the public /invoices ignores customer_id)",
          rc == 0 and paths == ["/jobs", "/jobs/job_abc/invoices"] and '"inv_1"' in out and '"job_number": "12109"' in out,
          (paths, out[:300]))
    rc, out = run("schedule", "2026-10-03")
    sent = SEEN[-1]["req"]["params"]
    check("the schedule asks for the day without a sort HCP refuses, and sorts by start time here",
          rc == 0 and not any(p[0] == "sort_by" for p in sent) and out.index('"j1"') < out.index('"j2"'), (sent, out))
    rc, out = run("get", "web", "/alpha/customer_service_agreements", "customer_id=cus_1")
    check("get passes name=value params", rc == 0 and SEEN[-1]["req"]["params"] == [["customer_id", "cus_1"]], SEEN[-1])
    rc, out = run("get", "web", "/alpha/x", "oops")
    check("a param without = is refused before anything is sent", rc == 2, out)
    rc, out = run("get", "web", "/alpha/big")
    check("a huge answer is cut, and says how to ask for less", rc == 0 and "cut at 60000" in out and len(out) < 61000,
          len(out))
    MODE.update(code=503, error="the house's Housecall Pro session is being refreshed; try again in a minute")
    rc, out = run("customers", "Garza")
    check("a refreshing session is exit 7 and 'try again', never an empty answer", rc == 7 and "try again" in out, out)
    MODE.update(code=403, error="this reader does not open /api/sessions")
    rc, out = run("get", "web", "/api/sessions")
    check("a refusal is exit 5 and names what was refused", rc == 5 and "does not open" in out, out)
    MODE.update(code=200)
    sk = open(SKILL, encoding="utf-8").read()
    check("the skill tells Claude never to say Housecall Pro is not connected, nor to ask for a login",
          "never say \"I'm not connected to Housecall Pro\"" in sk and "never ask for an HCP login" in sk, sk[:400])
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    srv.shutdown()

print("\n%d FAILED" % len(fails) if fails else "\nALL PASS")
sys.exit(1 if fails else 0)

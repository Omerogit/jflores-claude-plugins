"""The refocus plugin's SessionStart note (hello.py): a connected computer is told the Brain is reached through the
door, not Google Drive (Omar, 2026-10-02).    python tests/test_hello.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELLO = os.path.join(ROOT, "plugins", "refocus", "scripts", "hello.py")
HOOKS = os.path.join(ROOT, "plugins", "refocus", "hooks", "hooks.json")
fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:400]), flush=True)
    if not cond:
        fails.append(name)


def run(env):
    r = subprocess.run([sys.executable, HELLO], input="{}", env=env, capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout


tmp = tempfile.mkdtemp(prefix="hello-")
try:
    RH = os.path.join(tmp, "refocus")
    env = dict(os.environ, REFOCUS_HOME=RH, REFOCUS_IGNORE_HOUSE_WATCH="1", PYTHONIOENCODING="utf-8")
    env.pop("OFFICE_SEAT", None)
    rc, out = run(env)
    check("not connected: silent", rc == 0 and out == "", out)
    os.makedirs(RH)
    with open(os.path.join(RH, "door.json"), "w", encoding="utf-8") as f:
        json.dump({"door": "https://example.test/brain", "key": "bd_secret", "partner": "omar-desk"}, f)
    rc, out = run(env)
    check("connected: names the desk and the door, says not Google Drive", rc == 0 and "IS connected, as omar-desk"
          in out and "https://example.test/brain" in out and "not reached\nthrough Google Drive" in out, out)
    check("the key is never printed", "bd_secret" not in out, out)
    check("the first session is handed the welcome, with every part Omero asked for",
          "J FLORES WELCOME" in out and all(w in out for w in ("Memory that lasts", "send this to Omero",
          "Approve / Decline", "password-manager", "Their own agents", "/steward:start", "does not give")), out)
    rc, out = run(env)
    check("the welcome comes once: the next session gets only the connection note",
          "IS connected" in out and "J FLORES WELCOME" not in out, out)
    with open(os.path.join(RH, "door.json"), "wb") as f:
        f.write(b"\xef\xbb\xbf" + json.dumps({"door": "https://x.test/brain", "key": "k", "partner": "p"}).encode())
    rc, out = run(env)
    check("a door.json with a BOM (PowerShell 5) still reads", "IS connected, as p" in out, out)
    henv = dict(env, OFFICE_SEAT="zen")
    henv.pop("REFOCUS_IGNORE_HOUSE_WATCH")
    rc, out = run(henv)
    check("an office seat: silent", rc == 0 and out == "", out)
    hk = json.load(open(HOOKS, encoding="utf-8"))["hooks"]["SessionStart"]
    check("wired for startup, resume and clear (the compact hand-off stays its own)",
          any(h.get("matcher") == "startup|resume|clear" and "hello.py" in h["hooks"][0]["command"] for h in hk)
          and any(h.get("matcher") == "compact" for h in hk), hk)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n%d FAILED" % len(fails) if fails else "\nALL PASS")
sys.exit(1 if fails else 0)

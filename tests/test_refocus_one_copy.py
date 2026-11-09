# -*- coding: utf-8 -*-
"""One refocus copy runs, never two (refocus 1.7.2, 2026-11-09). A laptop that added this marketplace and also gets the
org-synced copy from jflores-house-plugins would otherwise run every hook twice against the same ~/.claude/refocus
state. The marketplace copy yields to an org copy that is installed and not switched off; the org copy never yields.
Driven end to end through hello.py (a connected computer's SessionStart note) in throwaway homes; nothing touches this
machine's real ~/.claude.

    python tests/test_refocus_one_copy.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RF = os.path.join(REPO, "plugins", "refocus")
fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:600]), flush=True)
    if not cond:
        fails.append(name)


def hello(home, plugin_root):
    env = dict(os.environ, HOME=home, USERPROFILE=home, PYTHONIOENCODING="utf-8")
    for k in ("REFOCUS_ONE_COPY_OFF", "REFOCUS_IGNORE_HOUSE_WATCH", "REFOCUS_HOME", "OFFICE_SEAT"):
        env.pop(k, None)
    r = subprocess.run([sys.executable, os.path.join(plugin_root, "scripts", "hello.py")], input="{}", env=env,
                       capture_output=True, text=True, timeout=60)
    return r.stdout + r.stderr


def settings(home, enabled):
    with open(os.path.join(home, ".claude", "settings.json"), "w", encoding="utf-8") as f:
        json.dump({"enabledPlugins": enabled}, f)


tmp = tempfile.mkdtemp(prefix="refocus-one-copy-")
try:
    h = os.path.join(tmp, "a")
    os.makedirs(os.path.join(h, ".claude", "refocus"))
    with open(os.path.join(h, ".claude", "refocus", "door.json"), "w", encoding="utf-8") as f:
        json.dump({"door": "https://example.test/brain", "key": "k", "partner": "zz-desk"}, f)
    out = hello(h, RF)
    check("marketplace copy speaks when there is no org copy", "IS connected, as zz-desk" in out, out)

    org = os.path.join(h, ".claude", "plugins", "synced", "ff9c_de0d", "refocus")
    shutil.copytree(RF, org)
    man = os.path.join(os.path.dirname(org), "manifest.json")
    with open(man, "w", encoding="utf-8") as f:
        json.dump({"plugins": [{"name": "steward"}]}, f)
    out = hello(h, RF)
    check("a leftover synced folder the org manifest no longer lists does not silence this copy",
          "IS connected" in out, out)
    with open(man, "w", encoding="utf-8") as f:
        json.dump({"plugins": [{"name": "refocus"}]}, f)
    out = hello(h, RF)
    check("MUST-FAIL on 1.7.1: marketplace copy is silent beside an installed org copy", out == "", out)
    out = hello(h, org)
    check("the org copy itself speaks", "IS connected, as zz-desk" in out, out)

    settings(h, {"refocus@synced": False})
    out = hello(h, RF)
    check("marketplace copy speaks when the org copy is switched off", "IS connected" in out, out)
    settings(h, {"refocus@synced": True})
    out = hello(h, RF)
    check("marketplace copy is silent when the org copy is switched on", out == "", out)

    for s in ("hello", "watch", "resume"):
        src = open(os.path.join(RF, "scripts", s + ".py"), encoding="utf-8").read()
        check("%s.py steps aside first thing in main()" % s,
              re.search(r"\ndef main\(\):\n    if yields_to_org_copy\(\):\n        return", src) is not None)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n%s: %d failed" % ("FAIL" if fails else "PASS", len(fails)))
sys.exit(1 if fails else 0)

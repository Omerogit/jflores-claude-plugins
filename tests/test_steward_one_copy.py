# -*- coding: utf-8 -*-
"""One steward copy runs, never two (steward 1.1.4, 2026-11-09). A laptop that added this marketplace and also gets the
org-synced copy from jflores-house-plugins would otherwise run both hooks against the same ~/.claude/steward state and
post every interview turn twice. The marketplace copy yields to an org copy that is installed and not switched off;
the org copy never yields. Offline: throwaway homes, nothing touches this machine's real ~/.claude.

    python tests/test_steward_one_copy.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(REPO, "plugins", "steward")
fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:600]), flush=True)
    if not cond:
        fails.append(name)


def yields(home, plugin_root):
    env = dict(os.environ, HOME=home, USERPROFILE=home)
    env.pop("STEWARD_ONE_COPY_OFF", None)
    code = ("import sys; sys.path.insert(0, %r); import hook; print('YIELD' if hook.yields_to_org_copy() else 'RUN')"
            % os.path.join(plugin_root, "scripts"))
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    return r.stdout.strip() or r.stderr.strip()


def synced_copy(home, listed=True):
    d = os.path.join(home, ".claude", "plugins", "synced", "ff9c_de0d", "steward~g2")
    shutil.copytree(ST, d)
    with open(os.path.join(os.path.dirname(d), "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"plugins": [{"name": "steward"}] if listed else [{"name": "refocus"}]}, f)
    return d


def settings(home, enabled):
    with open(os.path.join(home, ".claude", "settings.json"), "w", encoding="utf-8") as f:
        json.dump({"enabledPlugins": enabled}, f)


tmp = tempfile.mkdtemp(prefix="steward-one-copy-")
try:
    s = os.path.join(tmp, "stale")
    os.makedirs(os.path.join(s, ".claude"))
    synced_copy(s, listed=False)
    check("a leftover synced folder the org manifest no longer lists does not silence this copy",
          yields(s, ST) == "RUN", yields(s, ST))

    h = os.path.join(tmp, "a")
    os.makedirs(os.path.join(h, ".claude"))
    check("marketplace copy runs when there is no org copy", yields(h, ST) == "RUN", yields(h, ST))

    org = synced_copy(h)
    check("marketplace copy yields to an installed org copy", yields(h, ST) == "YIELD", yields(h, ST))
    check("the org copy itself runs", yields(h, org) == "RUN", yields(h, org))

    settings(h, {"steward@synced": False, "steward@jflores": True})
    check("marketplace copy runs when the org copy is switched off", yields(h, ST) == "RUN", yields(h, ST))

    settings(h, {"steward@synced": True})
    check("marketplace copy yields when the org copy is switched on", yields(h, ST) == "YIELD", yields(h, ST))

    with open(os.path.join(h, ".claude", "settings.json"), "w", encoding="utf-8") as f:
        f.write("{not json")
    check("a broken settings.json still yields to an installed org copy", yields(h, ST) == "YIELD", yields(h, ST))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n%s: %d failed" % ("FAIL" if fails else "PASS", len(fails)))
sys.exit(1 if fails else 0)

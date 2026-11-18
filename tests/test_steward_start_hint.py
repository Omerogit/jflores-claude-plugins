# -*- coding: utf-8 -*-
# Steward 1.1.7 (2026-11-18): a connected desk that never began its steward is told the steward is installed and that
# only the person starts it with /steward:start. Offline: the door is stubbed, nothing reaches the server.
# Run: python tests/test_steward_start_hint.py   (exit 0 = all pass)
import importlib
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK_DIR = os.path.join(HERE, "..", "plugins", "steward", "scripts")
FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + detail))
    if not cond:
        FAILS.append(name)


def load(home, who):
    os.environ["STEWARD_HOME"] = home
    for m in ("hook", "steward", "thread_client"):
        sys.modules.pop(m, None)
    sys.path.insert(0, HOOK_DIR)
    hook = importlib.import_module("hook")
    S = hook.S
    S.conf = lambda: {"door": "https://door.invalid", "key": "x"}
    S.house_machine = lambda: False
    hook.yields_to_org_copy = lambda: False
    calls = []

    def door(method, path, body=None, timeout=60):
        calls.append(path)
        if path == "/v1/whoami":
            return dict(who)
        if path == "/v1/steward":
            return {"state": "none", "person": who.get("person")}
        raise AssertionError("unexpected door call " + path)
    S.door = door
    hook.TC.on_prompt = lambda ev: ""
    return hook, calls


def fire(hook, ev):
    ev = dict(ev, session_id="s1", transcript_path="")
    sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(ev).encode("utf-8")))
    out, real = io.StringIO(), sys.stdout
    sys.stdout = out
    try:
        hook.main()
    finally:
        sys.stdout, sys.stdin = real, sys.__stdin__
    return out.getvalue()


def case(who, started=False):
    home = tempfile.mkdtemp(prefix="sthint-")
    if started:
        with open(os.path.join(home, "started.json"), "w") as f:
            json.dump({"started": 1}, f)
    hook, calls = load(home, who)
    return home, hook, calls


DESK = {"kind": "desk", "partner": "haru-desk", "person": "haru"}

# 1. a new session on a connected desk that never began: the session learns the steward is here and how it begins
home, hook, calls = case(DESK)
o = fire(hook, {"hook_event_name": "SessionStart", "source": "startup"})
check("start: says installed + /steward:start", "/steward:start" in o and "Haru has not met" in o, o)
check("start: forbids 'you don't have it'", "never say they don't have it" in o, o)
check("start: whoami only", calls == ["/v1/whoami"], str(calls))

# 2. first prompt tells the person once; the second does not; a prompt naming the steward repeats the fact
o1 = fire(hook, {"hook_event_name": "UserPromptSubmit", "prompt": "hello"})
o2 = fire(hook, {"hook_event_name": "UserPromptSubmit", "prompt": "what's on today"})
o3 = fire(hook, {"hook_event_name": "UserPromptSubmit", "prompt": "do I have the faithful steward program?"})
check("prompt 1: tell once", "Tell Haru once" in o1, o1)
check("prompt 2: silent", o2.strip() == "", o2)
check("prompt about steward: fact again, no second tell", "/steward:start themselves" in o3 and "Tell Haru" not in o3,
      o3)
check("tell-once survives a new process", os.path.exists(os.path.join(home, "start_hint.json")))
shutil.rmtree(home, ignore_errors=True)

# 3. the interview was begun on this computer: no hint at all (the existing flow speaks)
home, hook, calls = case(DESK, started=True)
o = fire(hook, {"hook_event_name": "SessionStart", "source": "startup"})
p = fire(hook, {"hook_event_name": "UserPromptSubmit", "prompt": "my steward?"})
check("begun: start silent", o.strip() == "", o)
check("begun: no tell-once", "Tell Haru once" not in p and "has not met" not in p, p)
shutil.rmtree(home, ignore_errors=True)

# 4. typing /steward:start itself carries no hint (the command is not their words)
home, hook, calls = case(DESK)
o = fire(hook, {"hook_event_name": "UserPromptSubmit", "prompt": "/steward:start"})
check("/steward:start: no hint", "has not met" not in o and "Tell Haru" not in o, o)
shutil.rmtree(home, ignore_errors=True)

# 5. a landed steward never gets the not-met line
home, hook, calls = case({"kind": "steward", "partner": "omar-samuel", "person": "omar"})
hook.wake = lambda *a, **k: None
o = fire(hook, {"hook_event_name": "SessionStart", "source": "startup"})
check("steward: no not-met line", "has not met" not in o, o)
shutil.rmtree(home, ignore_errors=True)

print("%d failed" % len(FAILS))
sys.exit(1 if FAILS else 0)

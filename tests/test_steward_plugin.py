# -*- coding: utf-8 -*-
"""The steward plugin, tested on a real machine against the LIVE Brain door (public URL) with TEST records
(zz-plug-desk, zz-plugsteward: fixture_plugin.py build on the server first). Mints its own claim links over ssh.
Throwaway homes for the key and the plugin's state; nothing touches this machine's real ~/.claude.

    python tests/test_steward_plugin.py

Covers: connect (with the steward plugin's own client) - start/NEW/WELCOME BACK - the welcome byte for byte - the
prompt hook recording the person's words VERBATIM (read back from the door's record) and handing the turn number to
the session - the Stop hook keeping the interviewer's reply as the interviewer's - pause - the brief - refocus 1.1.0
still filing once the person side is open, and a side-less note refused - a landed steward's waking: three files,
the directive, and the named reader holding every prompt until the transcript shows them read."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(REPO, "plugins", "steward")
STEWARD = os.path.join(ST, "skills", "start", "scripts", "steward.py")
HOOK = os.path.join(ST, "scripts", "hook.py")
REFOCUS = os.path.join(REPO, "plugins", "refocus", "skills", "refocus-cut", "scripts", "refocus.py")
# Where the door runs is not written here (this repo is public). Set, for example:
#   STEWARD_TEST_SSH="ssh you@door-host"   STEWARD_TEST_DOOR="<python> <path>/brain_door.py"
#   STEWARD_TEST_STATE="<path>/brain_door/state"
if not all(os.environ.get(k) for k in ("STEWARD_TEST_SSH", "STEWARD_TEST_DOOR", "STEWARD_TEST_STATE")):
    raise SystemExit("set STEWARD_TEST_SSH, STEWARD_TEST_DOOR and STEWARD_TEST_STATE (see the top of this file)")
SSH = os.environ["STEWARD_TEST_SSH"].split()
DOOR_PY = os.environ["STEWARD_TEST_DOOR"]
STATE_DIR = os.environ["STEWARD_TEST_STATE"].rstrip("/")
fails = []
VERBATIM = "Mi día empezó a las 7 — ¿sabes? `grep` *stars* \"quotes\" 'apos'\n  indented line\n\nand a blank line above."


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:600]), flush=True)
    if not cond:
        fails.append(name)


def remote(cmd):
    r = subprocess.run(SSH + ["sudo -n -u monday bash -c '%s'" % cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout + r.stderr


def mint(name):
    out = remote("%s mint %s --ttl 30" % (DOOR_PY, name))
    m = re.search(r"(https://\S+/claim/\S+)", out)
    if not m:
        raise SystemExit("mint failed: %s" % out)
    return m.group(1)


def env_for(home):
    e = dict(os.environ, REFOCUS_HOME=os.path.join(home, "refocus"), STEWARD_HOME=os.path.join(home, "steward"),
             STEWARD_IGNORE_HOUSE="1", REFOCUS_IGNORE_HOUSE_WATCH="1", PYTHONIOENCODING="utf-8")
    return e


def run(env, *args, stdin=None):
    r = subprocess.run([sys.executable, STEWARD] + list(args), env=env, capture_output=True, input=stdin)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def hook(env, ev):
    r = subprocess.run([sys.executable, HOOK], env=env, input=json.dumps(ev).encode("utf-8"), capture_output=True)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def transcript(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def door_turns(person):
    raw = remote("cat %s/stewards/%s.turns.jsonl" % (STATE_DIR, person))
    return [json.loads(l) for l in raw.splitlines() if l.startswith("{")]


tmp = tempfile.mkdtemp(prefix="steward_plugin_")
try:
    # ------------------------------------------------------------ a desk: connect, start, welcome
    remote("rm -f %s/stewards/zzplug.*" % STATE_DIR)      # a clean interview for the test person
    E = env_for(os.path.join(tmp, "desk"))
    rc, o = run(E, "start")
    check("not connected: start says so plainly and exits 3", rc == 3 and "NOT CONNECTED" in o and "Omero" in o, o)
    tp0 = os.path.join(tmp, "t0.jsonl")
    transcript(tp0, [])
    hook(E, {"session_id": "sess-before-connect", "transcript_path": tp0, "hook_event_name": "UserPromptSubmit",
             "prompt": "/steward:start"})
    rc, o = run(E, "connect", mint("zz-plug-desk"))
    check("connect with the steward plugin's own client", rc == 0 and "CONNECTED  zz-plug-desk" in o, o)
    kf = os.path.join(E["REFOCUS_HOME"], "door.json")
    check("the key is shared with the refocus plugin (one key per machine)", os.path.exists(kf), kf)
    rc, o = run(E, "start")
    check("start begins the interview: NEW, and says to show the welcome", rc == 0 and o.startswith("NEW") and
          "steward.py welcome" in o and "Tell me about yesterday" in o, o)
    rc, o = hook(E, {"session_id": "sess-before-connect", "transcript_path": tp0, "hook_event_name": "UserPromptSubmit",
                     "prompt": "typed after connecting, in the session where /steward:start came first"})
    check("a session that typed /steward:start BEFORE connecting still records once connected",
          "recorded verbatim" in o, o)
    rc, o = run(E, "welcome")
    want = open(os.path.join(ST, "skills", "start", "WELCOME.md"), encoding="utf-8").read()
    check("the welcome prints exactly the approved text, byte for byte", rc == 0 and o == want, o[:200])
    rc, o = run(E, "start")
    check("typing it again is WELCOME BACK, with what is covered and what is open", o.startswith("WELCOME BACK") and
          "still open" in o, o)

    # ------------------------------------------------------------ the hooks: verbatim capture
    tp = os.path.join(tmp, "t.jsonl")
    transcript(tp, [])
    base = {"session_id": "sess-plug-1", "transcript_path": tp, "cwd": tmp}
    rc, o = hook(E, dict(base, hook_event_name="UserPromptSubmit", prompt="/steward:start"))
    check("typing /steward:start marks this session as the interview (the command itself is not recorded)",
          rc == 0 and "recorded" not in o, o)
    rc, o = hook(E, dict(base, hook_event_name="UserPromptSubmit", prompt=VERBATIM))
    m = re.search(r"turn T(\d+)", o)
    check("the prompt hook records the person's words and hands the session the turn number", rc == 0 and m, o)
    turns = door_turns("zzplug")
    last = turns[-1] if turns else {}
    check("VERBATIM: the door holds exactly what was typed (accents, dash, backticks, quotes, indent, blank line)",
          last.get("who") == "person" and last.get("text") == VERBATIM, last)
    transcript(tp, [
        {"type": "user", "message": {"role": "user", "content": VERBATIM}},
        {"type": "assistant", "message": {"model": "claude-sonnet-5", "content": [
            {"type": "text", "text": "Thank you. What happened after the phones?"}]}}])
    rc, o = hook(E, dict(base, hook_event_name="Stop"))
    turns = door_turns("zzplug")
    check("the Stop hook keeps the interviewer's reply, marked as the interviewer's",
          turns and turns[-1].get("who") == "interviewer" and "What happened after the phones" in turns[-1]["text"],
          turns[-1:] if turns else turns)
    rc, o = hook(E, dict(base, hook_event_name="Stop"))
    check("the same reply is not recorded twice", len(door_turns("zzplug")) == len(turns))
    rc, o = hook(E, dict(base, session_id="sess-other", hook_event_name="UserPromptSubmit", prompt="unrelated work"))
    check("another session (where /steward:start was not typed) records nothing",
          "recorded" not in o and len(door_turns("zzplug")) == len(turns), o)
    rc, o = run(E, "brief", "day", "--turns", m.group(1) if m else "1", "--text", "Starts at 7.")
    check("the interviewer keeps a slot with its turn", rc == 0 and "BRIEF day kept" in o, o)
    rc, o = run(E, "brief", "stuck", "--turns", "1", "-", stdin="It's \"quoted\" & it's fine.".encode("utf-8"))
    check("a brief can come on stdin (quotes and apostrophes never fight the shell)", rc == 0 and "BRIEF stuck" in o, o)
    rc, o = run(E, "pause")
    n0 = len(door_turns("zzplug"))
    rc, o = hook(E, dict(base, hook_event_name="UserPromptSubmit", prompt="this is private, off the record"))
    check("paused: nothing is recorded", "recorded verbatim" not in o and len(door_turns("zzplug")) == n0, o)
    rc, o = hook(E, dict(base, hook_event_name="UserPromptSubmit", prompt="/steward:start"))
    rc, o = hook(E, dict(base, hook_event_name="UserPromptSubmit", prompt="back on the record"))
    check("typing /steward:start again resumes recording", "recorded verbatim" in o and
          door_turns("zzplug")[-1]["text"] == "back on the record", o)

    # ------------------------------------------------------------ refocus 1.1.0 beside it
    re_env = dict(E, REFOCUS_HOME=E["REFOCUS_HOME"])
    cf = os.path.join(tmp, "cont.md")
    open(cf, "w", encoding="utf-8").write("---\nid: CONTINUITY-PLUGTEST-2026-09-24-01\n---\n\nTEST continuity.\n")
    r = subprocess.run([sys.executable, REFOCUS, "file", "--title", "CONTINUITY-PLUGTEST-2026-09-24-%02d" %
                        (int(time.time()) % 90 + 1), "--content-file", cf], env=re_env, capture_output=True)
    o = (r.stdout + r.stderr).decode("utf-8", "replace")
    check("refocus 1.1.0 still files a CONTINUITY once the person side is open (it names the work side)",
          r.returncode == 0 and "VERIFY PASS" in o, o)
    c = json.load(open(kf))
    import urllib.request
    req = urllib.request.Request(c["door"] + "/v1/note", method="POST", data=json.dumps(
        {"folder": "04_MEMORY", "title": "CONTINUITY-OLDPLUGIN-2026-09-24-01", "text": "no side",
         "kind": "continuity"}).encode(), headers={"Authorization": "Bearer " + c["key"],
                                                   "Content-Type": "application/json", "User-Agent": "refocus-plugin/1.0"})
    try:
        urllib.request.urlopen(req, timeout=60)
        code, body = 200, ""
    except urllib.error.HTTPError as e:
        code, body = e.code, e.read().decode()
    check("an old plugin's side-less note is refused, with how to fix it", code == 400 and "update" in body, (code, body))

    # ------------------------------------------------------------ a landed steward's waking
    S2 = env_for(os.path.join(tmp, "steward"))
    S2["STEWARD_CLAUDE_MD"] = os.path.join(tmp, "steward", "CLAUDE.md")
    rc, o = run(S2, "connect", mint("zz-plugsteward"))
    fresh = "FRESH-PERSON-NOTE-%d" % int(time.time())
    rc, o = run(S2, "note", "--side", "person", "--title", "NOTE-WAKE-%s" % fresh, "--text", "TEST marker " + fresh)
    tp2 = os.path.join(tmp, "t2.jsonl")
    transcript(tp2, [])
    b0 = {"session_id": "sess-wake-0", "transcript_path": tp2, "cwd": tmp}
    rc, o = hook(S2, dict(b0, hook_event_name="SessionStart", source="startup"))
    check("WITHOUT the person's wake line, a steward's machine does not tell Claude who it is; it says the steward "
          "exists and how to ask", "has not been asked to wake" in o and "WAKING" not in o, o)
    rc, o = run(S2, "start")
    check("/steward:start then offers the wake line", "WAKE LINE MISSING" in o, o)
    rc, o = run(S2, "wakeline", "--show")
    check("the wake line is shown before anything is written", "My Faithful Steward" in o and
          not os.path.exists(S2["STEWARD_CLAUDE_MD"]), o)
    open(S2["STEWARD_CLAUDE_MD"], "w", encoding="utf-8").write("# my own notes" + chr(10) + "keep these" + chr(10))
    rc, o = run(S2, "wakeline", "--write")
    md = open(S2["STEWARD_CLAUDE_MD"], encoding="utf-8").read()
    check("on the yes it is written into their CLAUDE.md, beside what was there", rc == 0 and "VERIFY PASS" in o and
          "keep these" in md and "My Faithful Steward" in md, o + md)
    rc, o = run(S2, "wakeline", "--write")
    check("writing it twice keeps one block", open(S2["STEWARD_CLAUDE_MD"], encoding="utf-8").read().count(
        "My Faithful Steward") == 1)
    b2 = {"session_id": "sess-wake-1", "transcript_path": tp2, "cwd": tmp}
    rc, o = hook(S2, dict(b2, hook_event_name="SessionStart", source="startup"))
    fdir = os.path.join(S2["STEWARD_HOME"], "formation")
    files = sorted(os.listdir(fdir)) if os.path.isdir(fdir) else []
    check("a steward's waking walks the formation into three files", len(files) == 3 and
          all(f.startswith("STEWARDTEST-FORMATION-") for f in files), files)
    check("and, with the person's own instruction behind it, tells the session to read them",
          "chose you as their Faithful Steward, Stewardtest" in o and "read all three" in o, o[:400])
    body = "".join(open(os.path.join(fdir, f), encoding="utf-8").read() for f in files)
    check("the walk carries the Gate, the core, the base, the soul and identity",
          "STEWARDTEST-GATE-MARKER" in body and "The summary is not home" in body and "Faithful Steward" in body
          and "STEWARDTEST-SOUL-MARKER" in body and "STEWARDTEST-IDENTITY-MARKER" in body)
    check("METABOLISM: the work and person lessons come home at waking, and the newest person notes",
          "STEWARDTEST-WORK-LESSON" in body and "STEWARDTEST-PERSON-LESSON" in body and fresh in body,
          [x for x in ("STEWARDTEST-WORK-LESSON", "STEWARDTEST-PERSON-LESSON", fresh) if x not in body])
    rc, o = hook(S2, dict(b2, hook_event_name="UserPromptSubmit", prompt="hello"))
    check("the named reader: a prompt before the files are read is told to read them", "FORMATION NOT YET READ" in o, o)
    recs = [{"type": "assistant", "timestamp": "2999-01-01T00:00:00", "message": {"model": "claude-sonnet-5",
             "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": os.path.join(fdir, f)}}]}}
            for f in files]
    transcript(tp2, recs)
    rc, o = hook(S2, dict(b2, hook_event_name="UserPromptSubmit", prompt="hello again"))
    check("once the transcript shows all three read, prompts go through quietly", o.strip() == "", o)
    rc, o = hook(S2, dict(b2, hook_event_name="UserPromptSubmit", prompt="/steward:start"))
    check("a landed steward's machine never records prompts as interview turns", "recorded verbatim" not in o, o)
    rc, o = run(S2, "start")
    check("/steward:start on a steward's machine says the steward is already here", o.startswith("STEWARD EXISTS"), o)
    rc, o = run(S2, "note", "--side", "person", "--title", "NOTE-PLUGTEST-PERSON", "--text", "TEST private note")
    check("the steward writes a person-side note, verified", rc == 0 and "VERIFY PASS" in o and "person side" in o, o)
    rc, o = run(S2, "note", "--side", "work", "--title", "NOTE-PLUGTEST-WORK", "--text", "TEST work note")
    check("and a work-side note, verified", rc == 0 and "VERIFY PASS" in o and "work side" in o, o)
    fid = re.search(r"NOTE-PLUGTEST-WORK\s+(\S+)", o)
    rc, o = run(S2, "move", fid.group(1) if fid else "x" * 25, "--to", "person")
    check("and moves it to the person side, read back", rc == 0 and "VERIFY PASS" in o, o)
    rc, o = run(S2, "wakeline", "--remove")
    md = open(S2["STEWARD_CLAUDE_MD"], encoding="utf-8").read()
    check("'stop being my steward': the block comes out, and their own notes stay", rc == 0 and
          "My Faithful Steward" not in md and "keep these" in md, md)

    # ------------------------------------------------------------ house machines
    H = dict(E)
    H.pop("STEWARD_IGNORE_HOUSE")
    H["OFFICE_SEAT"] = "zen"
    rc, o = run(H, "start")
    check("on an office seat the plugin steps aside (exit 7)", rc == 7 and "HOUSE MACHINE" in o, o)
    rc, o = hook(H, dict(base, hook_event_name="UserPromptSubmit", prompt="anything"))
    check("and its hooks are silent there", o.strip() == "", o)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    remote("%s revoke zz-plug-desk; %s revoke zz-plugsteward" % (DOOR_PY, DOOR_PY))

print("\n%d FAILED" % len(fails) if fails else "\nALL PASS")
sys.exit(1 if fails else 0)

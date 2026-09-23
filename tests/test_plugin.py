"""The refocus plugin, tested on a real machine against the live Brain door with the TEST partner zz-doortest.
    python tests/test_plugin.py <one-time claim link for zz-doortest>
Uses a scratch REFOCUS_HOME and a scratch project folder; never touches ~/.claude/refocus."""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUG = os.path.join(ROOT, "plugins", "refocus")
RF = os.path.join(PLUG, "skills", "refocus-cut", "scripts", "refocus.py")
WATCH = os.path.join(PLUG, "scripts", "watch.py")
RESUME = os.path.join(PLUG, "scripts", "resume.py")
PYSH = os.path.join(PLUG, "scripts", "py.sh")
link = sys.argv[1]
tmp = tempfile.mkdtemp(prefix="refocus-")
RH = os.path.join(tmp, "state")
proj = os.path.join(tmp, "plugin-test-%d" % int(time.time()))
os.makedirs(proj)
LINE = os.path.basename(proj).upper()
today = datetime.date.today().isoformat()
fails = []
ENV = dict(os.environ, REFOCUS_HOME=RH, PYTHONIOENCODING="utf-8", REFOCUS_IGNORE_HOUSE_WATCH="1")
ENV.pop("OFFICE_SEAT", None)
HENV = dict(ENV)                     # the house check left ON: what an office seat or Omero's bench really sees
HENV.pop("REFOCUS_IGNORE_HOUSE_WATCH")


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:600]), flush=True)
    if not cond:
        fails.append(name)


def rf(*args, env=None):
    r = subprocess.run([sys.executable, RF] + list(args), cwd=proj, env=env or ENV, capture_output=True,
                       text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def hook(script, ev, env=None):
    r = subprocess.run([sys.executable, script], input=json.dumps(ev), env=env or ENV, capture_output=True,
                       text=True, encoding="utf-8", cwd=proj)
    return r.returncode, r.stdout


# ---------------------------------------------------------------- the client
rc, o = rf("whoami")
check("not connected: exit 3 and the loud STOP", rc == 3 and "NO BRAIN CONNECTED" in o and "Tell Omero" in o, o)
rc, o = rf("connect", "https://evil.example.com/steal")
check("connect refuses something that is not a Brain link", rc != 0 and "not a Brain link" in o, o)
rc, o = rf("connect", link)
check("connect with the one-time link", rc == 0 and "CONNECTED  zz-doortest" in o, o)
conf = os.path.join(RH, "door.json")
if os.name != "nt":
    check("the key file is 0600", oct(os.stat(conf).st_mode)[-3:] == "600", oct(os.stat(conf).st_mode))
rc, o = rf("connect", link)
check("the same link cannot be used twice", rc == 5 and "already used" in o, o)
rc, o = rf("whoami")
check("whoami names the desk and this folder's line", rc == 0 and "zz-doortest" in o and LINE in o, o)
rc, o = rf("method")
check("the method is read live from the Brain", rc == 0 and "AMENDMENT-CONTINUITY-SHARPENS" in o and len(o) > 2000, o[:300])
rc, o = rf("previous")
t1 = "CONTINUITY-%s-%s-01" % (LINE, today)
check("previous on a new line: NONE and the first title", rc == 0 and "NONE" in o and "NEXT TITLE  " + t1 in o, o)
body1 = "---\nid: %s\ntype: CONTINUITY\n---\n\n# first\nWhat governs the next move: test one. Quote: \"Keep it.\"\n" % t1
f1 = os.path.join(tmp, "c1.md")
open(f1, "w", encoding="utf-8", newline="").write(body1)
rc, o = rf("file", "--title", t1, "--content-file", f1)
id1 = next((l.split()[-1] for l in o.splitlines() if l.strip().startswith("FILEID")), None)
check("file: VERIFY PASS, three hashes", rc == 0 and "VERIFY PASS" in o and "HERE" in o and id1, o)
check("file: nothing older on a new line", "nothing older" in o, o)
rc, o = rf("file", "--title", t1, "--content-file", f1)
check("filing the same title twice is refused", rc != 0 and "already exists" in o, o)
rc, o = rf("file", "--title", "NOTES-FOR-ME", "--content-file", f1)
check("a title that is not CONTINUITY-<LINE>-date-NN is refused", rc != 0 and "title must be" in o, o)
open(os.path.join(tmp, "empty.md"), "w").write("  \n")
rc, o = rf("file", "--title", "CONTINUITY-%s-%s-09" % (LINE, today), "--content-file", os.path.join(tmp, "empty.md"))
check("an empty CONTINUITY is refused", rc != 0 and "empty" in o, o)
rc, o = rf("previous")
t2 = "CONTINUITY-%s-%s-02" % (LINE, today)
check("previous prints the latest, whole, and the next title", rc == 0 and "test one" in o and "NEXT TITLE  " + t2 in o, o)
f2 = os.path.join(tmp, "c2.md")
open(f2, "w", encoding="utf-8", newline="").write(body1.replace("# first", "# second").replace(t1, t2))
rc, o = rf("file", "--title", t2, "--content-file", f2)
id2 = next((l.split()[-1] for l in o.splitlines() if l.strip().startswith("FILEID")), None)
check("the second files and the first moves to _HISTORY", rc == 0 and "VERIFY PASS" in o and "1 older CONTINUITY moved" in o, o)
rc, o = rf("sweep")
check("sweep: one per line already, nothing to move", rc == 0 and "keep  " + t2 in o and "move" not in o.split("keep")[1], o)
rc, o = rf("read", id1)
check("the retired one still opens by its id", rc == 0 and "test one" in o, o)
rc, o = rf("read", "1PE3DepBIXhMJN0Zt8pE0dlBhL4ZwbMuv")
check("a house file outside the desk is refused", rc == 5 and "refused" in o, o)
rc, o = rf("cut", "--continuity-id", id2, "--name", t2)
check("cut says NOT CUT and to type /compact", rc == 0 and "NOT CUT" in o and "Type /compact now" in o, o)
rc, o = hook(RESUME, {"hook_event_name": "SessionStart", "source": "compact", "cwd": proj})
check("after /compact the hand-off names the CONTINUITY and how to read it", t2 in o and id2 in o and "read" in o, o)
rc, o = hook(RESUME, {"hook_event_name": "SessionStart", "source": "compact", "cwd": tmp})
check("another folder gets no hand-off", o == "", o)
ev_r = {"hook_event_name": "SessionStart", "source": "compact", "cwd": proj, "session_id": "dup-r"}
o1, o2 = hook(RESUME, ev_r)[1], hook(RESUME, ev_r)[1]
check("installed twice: the hand-off is said once, not twice", (t2 in o1) and o2 == "", [o1[:80], o2[:80]])
rc, o = rf("quiet")
check("quiet on", rc == 0 and "quiet ON" in o and os.path.exists(os.path.join(RH, "quiet.json")), o)
rc, o = rf("quiet", "--status")
check("quiet status", "ON" in o, o)
rc, o = rf("quiet", "--off")
check("quiet off", rc == 0 and not os.path.exists(os.path.join(RH, "quiet.json")), o)


# ---------------------------------------------------------------- the watch
def transcript(recs):
    p = os.path.join(tmp, "t%d.jsonl" % len(os.listdir(tmp)))
    with open(p, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    return p


def a(model, tokens):
    return {"type": "assistant", "message": {"model": model, "usage": {"input_tokens": 10,
            "cache_read_input_tokens": tokens, "cache_creation_input_tokens": 0}, "content": []}}


WENV = dict(ENV, REFOCUS_IGNORE_HOUSE_WATCH="1")


def watch(tp, sid, env=None):
    return hook(WATCH, {"hook_event_name": "UserPromptSubmit", "session_id": sid, "transcript_path": tp}, env or WENV)[1]


o = watch(transcript([a("claude-opus-5-5", 300000)]), "w1")
check("30% of a 1M window: silent", o == "", o)
t_hi = transcript([a("claude-opus-5-5", 500000)])
o = watch(t_hi, "w2")
check("50%: fires, with the four things and two samples", "about 50% full" in o and "stop asking" in o and
      o.count("  - ") == 2 and "NEVER /clear" in o, o)
check("the samples are not the same sentence twice", len(set(l for l in o.splitlines() if l.startswith("  - "))) == 2, o)
o = watch(t_hi, "w2")
check("it fires once, not every prompt", o == "", o)
watch(transcript([a("claude-opus-5-5", 100000)]), "w2")
o = watch(t_hi, "w2")
check("after the window drops (a compaction) it re-arms", "about 50% full" in o, o)
open(os.path.join(RH, "quiet.json"), "w").write("{}")
o = watch(t_hi, "w3")
check("quiet: silent", o == "", o)
os.remove(os.path.join(RH, "quiet.json"))
ev_d = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "dup-w", "transcript_path": t_hi})
procs = [subprocess.Popen([sys.executable, WATCH], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=WENV,
                          text=True, encoding="utf-8") for _ in range(2)]
outs = [p.communicate(ev_d)[0] for p in procs]
check("installed twice, both hooks at once: the person is asked exactly once",
      sum(1 for x in outs if "about 50% full" in x) == 1, [x[:60] for x in outs])
o = watch(transcript([a("claude-fable-5-1", 120000)]), "w4")
check("fable's measured window (280k): 120k fires", "43% full" in o or "42% full" in o, o)
o = watch(transcript([a("claude-sonnet-5", 90000)]), "w5")
check("an unknown window defaults small (200k): 90k fires", "45% full" in o, o)
o = watch(transcript([a("claude-opus-5-5", 500000), a("<synthetic>", 5000)]), "w6")
check("<synthetic> is skipped, the real record counts", "about 50% full" in o, o)
o = watch(transcript([a("claude-opus-5-5", 500000), {"type": "system", "subtype": "compact_boundary"}]), "w7")
check("a compaction after the last usage: silent (unknown beats wrong)", o == "", o)
o = watch(t_hi, "w8", env=dict(WENV, OFFICE_SEAT="zen"))
check("an office seat: silent (it has its own watch)", o == "", o)
empty = dict(WENV, REFOCUS_HOME=os.path.join(tmp, "nobrain"))
o = watch(t_hi, "w9", env=empty)
check("no brain connected: it says so and does not offer the refocus", "NO BRAIN CONNECTED" in o and
      "Do not file or cut" in o and "about 50% full" in o, o)
if os.path.exists(os.path.join(os.path.expanduser("~"), ".claude", "hooks", "context_watch.py")):
    o = watch(t_hi, "w10", env=HENV)
    check("on Omero's machine (house watch present): silent, never twice", o == "", o)
    rc, o = rf("whoami", env=HENV)
    check("on Omero's bench the skill steps aside to the house refocus-cut (exit 7)",
          rc == 7 and "HOUSE MACHINE" in o and "`refocus-cut`" in o, o)

# ---------------------------------------------------------------- house machines: the plugin steps aside
SEAT = dict(HENV, OFFICE_SEAT="zen", OFFICE_ROOM="r1")
rc, o = rf("whoami", env=SEAT)
check("on an office seat the skill steps aside to the house refocus-cut (exit 7), files nothing",
      rc == 7 and "office seat (zen)" in o, o)
rc, o = rf("file", "--title", "CONTINUITY-%s-%s-07" % (LINE, today), "--content-file", f1, env=SEAT)
check("on an office seat even `file` refuses before touching the door", rc == 7, o)
rc, o = hook(RESUME, {"hook_event_name": "SessionStart", "source": "compact", "cwd": proj, "session_id": "seat"}, SEAT)
check("on an office seat the plugin's hand-off stays silent (the house hook speaks)", o == "", o)
o = watch(t_hi, "w11", env=SEAT)
check("on an office seat the plugin's watch stays silent", o == "", o)

# ---------------------------------------------------------------- py.sh
sh = shutil.which("sh")
if sh:
    r = subprocess.run([sh, PYSH, "watch.py"], input=json.dumps({"hook_event_name": "UserPromptSubmit",
                       "session_id": "p1", "transcript_path": t_hi}), env=WENV, capture_output=True, text=True)
    check("py.sh finds a working Python and runs the hook", "about 50% full" in r.stdout, r.stdout + r.stderr)
    if os.name != "nt":
        nopy = os.path.join(tmp, "nopy")
        os.makedirs(nopy)
        for tool in ("dirname", "date", "mkdir", "sh"):
            p = shutil.which(tool)
            if p:
                os.symlink(p, os.path.join(nopy, tool))
        e2 = dict(WENV, PATH=nopy, HOME=os.path.join(tmp, "home2"))
        r = subprocess.run([os.path.join(nopy, "sh"), PYSH, "watch.py"], input="{}", env=e2, capture_output=True, text=True)
        check("no Python: one plain notice", "no working Python 3" in r.stdout and r.returncode == 0, r.stdout + r.stderr)
        r = subprocess.run([os.path.join(nopy, "sh"), PYSH, "watch.py"], input="{}", env=e2, capture_output=True, text=True)
        check("no Python: not repeated the same day", r.stdout == "", r.stdout)

shutil.rmtree(tmp, ignore_errors=True)
print("\n%d FAILED" % len(fails) if fails else "\nALL PASS")
sys.exit(1 if fails else 0)

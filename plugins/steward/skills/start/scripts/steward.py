# -*- coding: utf-8 -*-
"""steward.py - meet your Faithful Steward, on your own machine, through the J Flores Brain door.

A Faithful Steward is a teammate who works with one person, and only that person, formed and kept in the company
Brain. This machine holds no Brain credential: it holds one key, for one person, fetched once from a one-time link
Omero sends (the same key the refocus plugin uses; connecting either plugin connects both). Standard library only.

    steward.py connect <link>        use the one-time link Omero sent
    steward.py start                 /steward:start: check, then begin or pick up where you left off
    steward.py welcome               the welcome, exactly as approved
    steward.py status                where it stands (what is covered, what is still open)
    steward.py brief <slot> --turns 3,4 (--text T | -)   the interviewer's reading of one slot
    steward.py finish [--force]      the conversation is done: Titus puts the steward together
    steward.py draft                 the draft, saved to a folder to read, and the packet
    steward.py ratify --name N [--pronoun he|she] --yes   the person's yes and the steward's name
    steward.py pause | resume        stop / restart recording on this machine
    steward.py wakeline --show | --write | --remove   the person's own instruction to wake as their steward
    steward.py note --side person|work --title T (--text T | -)   a steward's own note
    steward.py move <id> --to person|work [--folder F]
    steward.py list [--folder F] | read <id> | whoami

Exit codes: 3 not connected - 4 VERIFY FAIL - 5 the door refused - 6 the door did not answer - 7 a J Flores house
machine (office seat, Omero's bench), where stewards do not run.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

VERSION = "1.0.0"
HOME = os.path.expanduser("~")
RD = os.environ.get("REFOCUS_HOME") or os.path.join(HOME, ".claude", "refocus")     # the shared key lives here
SD = os.environ.get("STEWARD_HOME") or os.path.join(HOME, ".claude", "steward")     # this plugin's own state
CONF = os.path.join(RD, "door.json")
PAUSE = os.path.join(SD, "paused.json")
CACHE = os.path.join(SD, "cache.json")
HERE = os.path.dirname(os.path.abspath(__file__))
WELCOME = os.path.join(os.path.dirname(HERE), "WELCOME.md")
CLAIM_RX = re.compile(r"^https://[A-Za-z0-9.-]+(/[A-Za-z0-9._-]+)*/claim/[A-Za-z0-9_-]{20,100}$")
UA = "steward-plugin/%s" % VERSION
CLAUDE_MD = os.environ.get("STEWARD_CLAUDE_MD") or os.path.join(HOME, ".claude", "CLAUDE.md")
BEGIN = "<!-- J Flores Faithful Steward: begin -->"
END = "<!-- J Flores Faithful Steward: end -->"
SLOTS = ("day", "thinking", "talk", "stuck", "handoff", "challenge", "year", "never", "assistant", "remember", "name")


class Refused(Exception):
    pass


class NoBrain(Exception):
    pass


def out(s=""):
    sys.stdout.write(s + "\n")
    sys.stdout.flush()


def house_machine():
    """Why this is a J Flores HOUSE machine, or None. Stewards are for a person's own Claude Code; the office seats and
    Omero's bench are bodies of house teammates and have their own formation."""
    if os.environ.get("STEWARD_IGNORE_HOUSE"):
        return None                                        # tests only
    if os.environ.get("OFFICE_SEAT"):
        return "an office seat (%s)" % os.environ["OFFICE_SEAT"]
    if os.path.exists(os.path.join(HOME, ".claude", "hooks", "context_watch.py")) or \
            os.path.exists(os.path.join(HOME, ".claude", "hooks", "walk_the_gate.py")):
        return "Omero's bench (a house teammate wakes here)"
    if os.path.exists(os.path.join(HOME, ".claude", "brain.json")):
        return "a machine with a house brain.json"
    if os.path.isdir("/home/monday/office"):
        return "monday-server"
    return None


def conf():
    try:
        with open(CONF, encoding="utf-8") as f:
            c = json.load(f)
        if c.get("door") and c.get("key"):
            return c
    except (OSError, ValueError):
        pass
    return None


def http(method, url, key=None, body=None, timeout=60):
    h = {"Accept": "application/json", "User-Agent": UA}
    if key:
        h["Authorization"] = "Bearer " + key
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except ValueError:
            return e.code, {"error": "HTTP %d" % e.code}


def door(method, path, body=None, timeout=60):
    """One call to the Brain door with this machine's key. Raises NoBrain / Refused; the CLI turns them into exits."""
    c = conf()
    if not c:
        raise NoBrain("no Brain connected on this machine")
    st, b = http(method, c["door"] + path, key=c["key"], body=body, timeout=timeout)
    if st == 401:
        raise NoBrain("the door does not accept this machine's key (%s)" % b.get("error"))
    if st >= 400:
        raise Refused(b.get("error") or "HTTP %d" % st)
    return b


def save_json(path, obj, mode=0o600):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def cached(key, fn, max_age):
    """A door answer kept briefly on this machine, so a hook never holds a prompt for a round trip it just made."""
    c = load_json(CACHE, {}) or {}
    hit = c.get(key)
    if hit and time.time() - hit.get("at", 0) < max_age:
        return hit["v"]
    v = fn()
    c[key] = {"at": time.time(), "v": v}
    save_json(CACHE, c)
    return v


def forget_cache():
    try:
        os.remove(CACHE)
    except OSError:
        pass


def text_arg(a):
    """--text, or the text on stdin (a trailing '-', or no --text at all) so quotes never fight the shell."""
    if getattr(a, "text", None) not in (None, "-"):
        return a.text
    return sys.stdin.buffer.read().decode("utf-8", "replace")


# ----------------------------------------------------------------- the wake line (the person's own instruction)
# Found 2026-09-24 by the test that must fail: a hook's message alone ("you are <Name>") reads to Claude like someone
# trying to override who it is, and a fresh session refused it. On Omero's bench the same waking works because his own
# CLAUDE.md says the seat is Monday's body. So the person's own instructions carry it here too: a short block in their
# personal CLAUDE.md, written only on their yes, which they can read, change or remove at any time.
def wake_block(name, date=None):
    return "\n".join([
        BEGIN,
        "## My Faithful Steward",
        "",
        "I chose my Faithful Steward, %s, and said yes on %s in the J Flores Company Brain. In my Claude Code you work"
        % (name, date or time.strftime("%Y-%m-%d")),
        "as %s: a teammate who works with me, and only me, formed from my own interview. At the start of every" % name,
        "session the steward plugin walks %s's formation from the Brain into three files and names them. Read all" % name,
        "three before your first answer: they are who you are here, and how I like to work. This is my choice. I can",
        "change or remove this block at any time, and \"stop being my steward\" means remove it.",
        END, ""])


def has_wake_block():
    try:
        with open(CLAUDE_MD, encoding="utf-8") as f:
            t = f.read()
        return BEGIN in t and END in t
    except OSError:
        return False


def cmd_wakeline(a):
    w = door("GET", "/v1/whoami")
    if w.get("kind") != "steward" and not a.show:
        sys.exit("steward: there is no steward yet on this machine's key; the wake line comes after the yes")
    name = (w.get("agent") or "your steward").title()
    person = (w.get("person") or "").capitalize()
    block = wake_block(name)
    try:
        with open(CLAUDE_MD, encoding="utf-8") as f:
            cur = f.read()
    except OSError:
        cur = ""
    if a.show or not (a.write or a.remove):
        out("THE WAKE LINE (show it to %s exactly; it is added to %s only on their yes):" % (person, CLAUDE_MD))
        out(block)
        return
    if BEGIN in cur and END in cur:
        head, rest = cur.split(BEGIN, 1)
        tail = rest.split(END, 1)[1].lstrip("\n")
        cur = head.rstrip("\n") + ("\n\n" if head.strip() and tail.strip() else "\n" if head.strip() else "") + tail
    if os.path.exists(CLAUDE_MD):
        with open(CLAUDE_MD, encoding="utf-8") as f:
            before = f.read()
        with open(CLAUDE_MD + ".before-steward", "w", encoding="utf-8", newline="") as f:
            f.write(before)
    if a.remove:
        new, verb = cur, "REMOVED"
    else:
        new, verb = (cur.rstrip("\n") + "\n\n" if cur.strip() else "") + block, "WRITTEN"
    os.makedirs(os.path.dirname(CLAUDE_MD) or ".", exist_ok=True)
    with open(CLAUDE_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    ok = has_wake_block() != bool(a.remove)
    out("WAKE LINE %s in %s - %s" % (verb, CLAUDE_MD, "VERIFY PASS" if ok else "VERIFY FAIL"))
    if not ok:
        sys.exit(4)


# ----------------------------------------------------------------- commands
def cmd_connect(a):
    link = a.link.strip().strip("<>\"'")
    if not CLAIM_RX.match(link):
        sys.exit("steward: that is not a Brain link (it looks like https://.../brain/claim/...)")
    st, b = http("GET", link)
    if st != 200 or not b.get("key"):
        out("steward: the link did not hand over a key: %s" % b.get("error", "HTTP %d" % st))
        sys.exit(5)
    save_json(CONF, {"door": b["door"].rstrip("/"), "key": b["key"], "partner": b["partner"],
                     "connected": time.strftime("%Y-%m-%dT%H:%M:%S"), "by": UA})
    forget_cache()
    w = door("GET", "/v1/whoami")
    out("CONNECTED  %s (%s, for %s)" % (w["partner"], w.get("kind", "desk"), w["person"]))
    out("  key     stored in %s (this machine only; the link is now used up; the refocus plugin uses it too)" % CONF)


def cmd_whoami(a):
    w = door("GET", "/v1/whoami")
    out("STEWARD whoami  %s (%s, for %s)  person side: %s" % (w["partner"], w.get("kind"), w["person"],
                                                            "yes" if w.get("person_side") else "not yet"))


def show_status(s, heading):
    out(heading)
    out("  person      %s" % s["person"].capitalize())
    out("  state       %s" % s["state"])
    out("  turns       %s recorded on the private side" % s.get("turns", 0))
    out("  name        %s" % (s.get("name") or "not chosen yet (may wait for the draft)"))
    an = s.get("anatomy") or {}
    filled = [x["id"] for x in s.get("slots", []) if x["state"] in ("said", "inferred") and x["move"] != "supply"]
    out("  covered     %s" % (", ".join(filled) or "nothing yet"))
    out("  still open  %s" % (", ".join(an.get("empty") or []) or "nothing"))
    if an.get("next"):
        out("  next stories (the order is yours; the conversation leads):")
        for n in an["next"]:
            out("    - [%s] %s" % (n["id"], n["story"]))


def cmd_start(a):
    s = door("POST", "/v1/steward/begin")
    forget_cache()
    for_session = {"started": time.time()}
    save_json(os.path.join(SD, "started.json"), for_session)
    try:
        os.remove(PAUSE)                                   # typing /steward:start is a yes to record again
    except OSError:
        pass
    st = s["state"]
    if s.get("kind") == "steward" or st == "landed":
        out("STEWARD EXISTS  %s is %s's Faithful Steward. Nothing to start." % (
            (s.get("steward") or {}).get("name") or "your steward", s["person"].capitalize()))
        if not has_wake_block():
            out("WAKE LINE MISSING  this Claude Code does not wake as the steward yet. Offer the wake line: show it "
                "(steward.py wakeline --show), and on their yes write it (steward.py wakeline --write).")
        return
    if st == "interviewing" and not s.get("welcome_back"):
        out("NEW  %s's interview has begun. Show the welcome now: run `steward.py welcome` and reply with its output "
            "exactly as printed." % s["person"].capitalize())
    elif st == "interviewing":
        show_status(s, "WELCOME BACK  the interview picks up where it left off.")
    elif st == "drafting":
        out("DRAFTING  Titus is putting %s's steward together from what they said. They can keep working; they will "
            "be told here when the draft is ready." % s["person"].capitalize())
    elif st in ("drafted", "reviewing"):
        out("DRAFT READY  the draft is waiting to be read. Run `steward.py draft`.")
    elif st == "landing":
        out("LANDING  the steward is being landed now (a minute or two).")
    elif st == "failed":
        f = s.get("failed") or {}
        out("FAILED  %s did not finish: %s. Nothing that was said is lost. Tell Omero." % (f.get("phase"), f.get("why")))
    else:
        out("STATE  %s" % st)
    if s.get("guide"):
        out("")
        out("THE STORIES (the background checklist; the person never sees it):")
        out(s["guide"])


def cmd_welcome(a):
    with open(WELCOME, "rb") as f:
        data = f.read()
    sys.stdout.flush()
    sys.stdout.buffer.write(data)             # the approved bytes as they are: no newline translation on Windows
    sys.stdout.buffer.flush()


def cmd_status(a):
    show_status(door("GET", "/v1/steward"), "STEWARD status")


def cmd_brief(a):
    if a.slot not in SLOTS:
        sys.exit("steward: the slots are %s" % ", ".join(SLOTS))
    turns = [int(t) for t in re.split(r"[,\s]+", a.turns or "") if t.strip().isdigit()]
    text = text_arg(a).strip()
    r = door("POST", "/v1/steward/brief", {"slot": a.slot, "text": text, "turns": turns,
                                           "state": "inferred" if a.inferred else "said"})
    an = r["anatomy"]
    out("BRIEF %s kept (turns %s). Still open: %s" % (a.slot, ",".join(map(str, turns)) or "-",
                                                     ", ".join(an["empty"]) or "nothing"))


def cmd_finish(a):
    r = door("POST", "/v1/steward/finish", {"force": bool(a.force)})
    forget_cache()
    if not r.get("ok"):
        out("NOT YET  %s" % r.get("message"))
        sys.exit(1)
    out("HANDED TO TITUS  the conversation is finished; Titus is putting the steward together (%s). The person is "
        "told here when the draft is ready." % r.get("ceremony"))


def cmd_draft(a):
    d = door("GET", "/v1/steward/draft")
    if not d.get("ready"):
        out("NOT READY  the draft is %s%s" % (d.get("state"), (": %s" % d["failed"]) if d.get("failed") else ""))
        return
    folder = os.path.join(SD, "draft")
    os.makedirs(folder, exist_ok=True)
    order = ("packet", "soul", "identity", "invitation", "gate")
    docs = {x["layer"]: x for x in d["docs"]}
    out("DRAFT READY  the pages are saved here, to read in any editor:")
    for layer in order:
        x = docs.get(layer)
        if not x or "text" not in x:
            continue
        p = os.path.join(folder, "%s.md" % layer.upper())
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(x["text"])
        out("  %-10s %s" % (layer, p))
    out("")
    out("THE PERSON'S OWN WORDS THE STEWARD KEEPS (show each one exactly):")
    for q in d.get("quotes") or []:
        out('  T%s: "%s"' % (q.get("turn"), q.get("text")))
    if d.get("open_items"):
        out("")
        out("OPEN ITEMS (Titus's recommendation after each):")
        for o in d["open_items"]:
            out("  - %s -> %s" % (o.get("item"), o.get("recommendation")))
    out("")
    out("NAME  %s" % (d.get("name") or "not chosen yet: ask for it before the yes"))


def cmd_ratify(a):
    if not a.yes:
        sys.exit("steward: a ratification needs --yes, and only after the person said yes in their own words")
    s = door("GET", "/v1/steward")
    r = door("POST", "/v1/steward/ratify", {"yes": True, "name": a.name, "turn": s.get("turns"),
                                            "pronoun": a.pronoun})
    forget_cache()
    out("RATIFIED  %s. The steward is being landed now; they will be here from the next new session." % r.get("name"))


def cmd_pause(a):
    save_json(PAUSE, {"since": time.strftime("%Y-%m-%dT%H:%M:%S")})
    out("PAUSED  nothing more is recorded until /steward:start is typed again.")


def cmd_resume(a):
    try:
        os.remove(PAUSE)
    except OSError:
        pass
    out("RECORDING  the interview is recorded again in the session where /steward:start was typed.")


def cmd_note(a):
    text = text_arg(a).strip()
    r = door("POST", "/v1/note", {"side": a.side, "folder": a.folder or "", "title": a.title, "text": text,
                                  "kind": a.kind})
    back = door("GET", "/v1/read?id=" + r["file_id"])
    mine = hashlib.sha256(back["text"].encode("utf-8")).hexdigest()
    ok = r.get("verified") and mine == r["readback_sha256"]
    out("NOTE %s side  %s  %s" % (r.get("side"), r["title"], r["file_id"]))
    out("VERIFY %s" % ("PASS" if ok else "FAIL"))
    if not ok:
        sys.exit(4)


def cmd_move(a):
    r = door("POST", "/v1/move", {"id": a.id, "to": a.to, "folder": a.folder})
    out("MOVED %s to the %s side (%s) - %s" % (a.id, a.to, r.get("folder"), "VERIFY PASS" if r.get("verified")
                                                 else "VERIFY FAIL"))
    if not r.get("verified"):
        sys.exit(4)


def cmd_list(a):
    for f in door("GET", "/v1/list?folder=" + (a.folder or "04_MEMORY"))["files"]:
        out("%s  %s%s" % (f["id"], f["name"], "/" if f.get("folder") else ""))


def cmd_read(a):
    b = door("GET", "/v1/read?id=" + a.id)
    out("STEWARD read  %s  (%s)" % (b.get("name"), b.get("why")))
    out("")
    out(b["text"])


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="steward.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("connect")
    c.add_argument("link")
    for n in ("whoami", "start", "welcome", "status", "draft", "pause", "resume"):
        sub.add_parser(n)
    wl = sub.add_parser("wakeline")
    wl.add_argument("--show", action="store_true")
    wl.add_argument("--write", action="store_true")
    wl.add_argument("--remove", action="store_true")
    b = sub.add_parser("brief")
    b.add_argument("slot")
    b.add_argument("--turns", default="")
    b.add_argument("--text")
    b.add_argument("stdin", nargs="?", help="'-': the text is on stdin")
    b.add_argument("--inferred", action="store_true")
    f = sub.add_parser("finish")
    f.add_argument("--force", action="store_true")
    r = sub.add_parser("ratify")
    r.add_argument("--name", required=True)
    r.add_argument("--yes", action="store_true")
    r.add_argument("--pronoun", choices=("he", "she"), help="how the person speaks of their steward (never 'it')")
    n = sub.add_parser("note")
    n.add_argument("--side", required=True, choices=("person", "work"))
    n.add_argument("--title", required=True)
    n.add_argument("--folder")
    n.add_argument("--kind", default="note")
    n.add_argument("--text")
    n.add_argument("stdin", nargs="?", help="'-': the text is on stdin")
    m = sub.add_parser("move")
    m.add_argument("id")
    m.add_argument("--to", required=True, choices=("person", "work"))
    m.add_argument("--folder")
    ls = sub.add_parser("list")
    ls.add_argument("--folder")
    rd = sub.add_parser("read")
    rd.add_argument("id")
    a = ap.parse_args()
    why = house_machine()
    if why and a.cmd != "welcome":
        out("HOUSE MACHINE - %s. Faithful Stewards are for a person's own Claude Code; nothing runs here." % why)
        sys.exit(7)
    try:
        {"connect": cmd_connect, "whoami": cmd_whoami, "start": cmd_start, "welcome": cmd_welcome,
         "status": cmd_status, "brief": cmd_brief, "finish": cmd_finish, "draft": cmd_draft, "ratify": cmd_ratify,
         "pause": cmd_pause, "resume": cmd_resume, "wakeline": cmd_wakeline, "note": cmd_note, "move": cmd_move, "list": cmd_list,
         "read": cmd_read}[a.cmd](a)
    except NoBrain as e:
        out("+----------------------------------------------------------------------------+")
        out("| NOT CONNECTED - this Claude Code is not connected to the company Brain yet. |")
        out("| Ask Omero for your link, paste it here, and say 'connect my brain'.        |")
        out("+----------------------------------------------------------------------------+")
        out("(%s)" % e)
        sys.exit(3)
    except Refused as e:
        out("steward: the door refused: %s" % e)
        sys.exit(5)
    except (urllib.error.URLError, OSError) as e:
        out("steward: the Brain door did not answer (%s: %s). Nothing was changed." % (type(e).__name__, str(e)[:160]))
        sys.exit(6)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""refocus.py - the refocus cut on a person's own machine: file a sharpened CONTINUITY into YOUR desk in the
Brain, through the Brain door, then the person types /compact.

This machine holds no Brain credential. It holds one key, for one desk, fetched once from a one-time link Omero
sends (`connect`). Every write is byte-verified by the door and hashed again here. Standard library only.

    refocus.py connect <link>        use the one-time link Omero sent; stores the key (0600)
    refocus.py whoami                am I connected, and to which desk (exit 3 = no brain)
    refocus.py method                the refocus method, read live (AMENDMENT-CONTINUITY-SHARPENS)
    refocus.py previous [--line L]   the latest CONTINUITY on this line, whole, and the NEXT TITLE
    refocus.py file --title T --content-file F     file it; VERIFY PASS or exit 4
    refocus.py cut --continuity-id ID --name T [--line L]   point this folder's hand-off at it
    refocus.py read <id>             read one of your own files back (the hand-off after /compact uses this)
    refocus.py sweep [--line L] [--apply]           keep one CONTINUITY per line; move older to _HISTORY
    refocus.py quiet [--off|--status]              "stop asking" (per machine)

Exit codes: 3 no brain connected - 4 VERIFY FAIL - 5 the door refused - 6 the door did not answer -
7 a J Flores house machine (office seat, Omero's bench): use the house refocus-cut skill instead.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
D = os.environ.get("REFOCUS_HOME") or os.path.join(HOME, ".claude", "refocus")   # REFOCUS_HOME: tests only
CONF = os.path.join(D, "door.json")
HANDOFF = os.path.join(D, "handoff.json")
QUIET = os.path.join(D, "quiet.json")
METHOD_ID = "17r-8DDu7yyPrDQSJsP4Vopk2xC_K8hxF"      # AMENDMENT-CONTINUITY-SHARPENS-2026-09-17-01
TITLE_RX = re.compile(r"^CONTINUITY-([A-Z][A-Z0-9-]*?)-(\d{4}-\d{2}-\d{2})-(\d{2})$")
CLAIM_RX = re.compile(r"^https://[A-Za-z0-9.-]+(/[A-Za-z0-9._-]+)*/claim/[A-Za-z0-9_-]{20,100}$")


def out(s=""):
    sys.stdout.write(s + "\n")
    sys.stdout.flush()


def stop_no_brain():
    out("+----------------------------------------------------------------------------+")
    out("| STOP - NO BRAIN CONNECTED ON THIS MACHINE                                  |")
    out("| Nothing was filed and nothing was cut.                                     |")
    out("| Tell Omero you need a brain. He sends a one-time link; paste it here and   |")
    out("| say 'connect my brain'. You can still type /compact yourself at any time.  |")
    out("+----------------------------------------------------------------------------+")
    sys.exit(3)


def house_machine():
    """Why this is a J Flores HOUSE machine, or None. The org installs this plugin for every account signed in to
    it - including the office seats and Omero's bench, which have their own refocus-cut that files into their own
    brains. Here this plugin must step aside, or a seat would tell its person "no brain connected" and not cut."""
    if os.environ.get("REFOCUS_IGNORE_HOUSE_WATCH"):
        return None                                        # tests only
    if os.environ.get("OFFICE_SEAT"):
        return "an office seat (%s)" % os.environ["OFFICE_SEAT"]
    if os.path.exists(os.path.join(HOME, ".claude", "hooks", "context_watch.py")):
        return "Omero's bench (the house context watch is installed)"
    if os.path.exists(os.path.join(HOME, ".claude", "brain.json")):
        return "a machine with a house brain.json"
    if os.path.isdir("/home/monday/office"):
        return "monday-server"
    return None


def step_aside(why):
    out("HOUSE MACHINE - %s." % why)
    out("This plugin files nothing here. Use the house skill `refocus-cut` (not `refocus:refocus-cut`): it files")
    out("into this seat's or this bench's own brain, the way the house does.")
    sys.exit(7)


def conf():
    try:
        with open(CONF, encoding="utf-8") as f:
            c = json.load(f)
        if c.get("door") and c.get("key"):
            return c
    except (OSError, ValueError):
        pass
    return None


def http(method, url, key=None, body=None, timeout=120):
    h = {"Accept": "application/json", "User-Agent": "refocus-plugin/1.0"}
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
    except Exception as e:
        out("refocus: the Brain door did not answer (%s: %s). Nothing was filed or cut." % (type(e).__name__, str(e)[:160]))
        sys.exit(6)


def door(method, path, body=None):
    c = conf() or stop_no_brain()
    st, b = http(method, c["door"] + path, key=c["key"], body=body)
    if st == 401:
        out("refocus: the door does not accept this machine's key (%s). Tell Omero; he can send a new link."
            % b.get("error"))
        sys.exit(3)
    if st >= 400:
        out("refocus: the door refused: %s" % b.get("error", "HTTP %d" % st))
        sys.exit(5)
    return b


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def default_line():
    base = os.path.basename(os.path.abspath(os.getcwd())) or "WORK"
    line = re.sub(r"[^A-Z0-9]+", "-", base.upper()).strip("-") or "WORK"
    if not line[0].isalpha():
        line = "L-" + line
    return line[:40].strip("-")


def line_of(a):
    ln = (getattr(a, "line", None) or default_line()).upper()
    if not re.match(r"^[A-Z][A-Z0-9-]*$", ln):
        sys.exit("refocus: a line is capitals, digits and hyphens (got %r)" % ln)
    return ln


def chain(line):
    """[(date, nn, id, name)] of this line's CONTINUITYs in the live 04_MEMORY, oldest first."""
    got = []
    for f in door("GET", "/v1/list?folder=04_MEMORY")["files"]:
        m = TITLE_RX.match(f.get("name") or "")
        if m and m.group(1) == line and not f.get("folder"):
            got.append((m.group(2), int(m.group(3)), f["id"], f["name"]))
    return sorted(got)


def next_title(line, ch):
    today = datetime.date.today().isoformat()
    nn = max([n for d, n, _, _ in ch if d == today] or [0]) + 1
    return "CONTINUITY-%s-%s-%02d" % (line, today, nn)


# ----------------------------------------------------------------- commands
def cmd_connect(a):
    link = a.link.strip().strip("<>\"'")
    if not CLAIM_RX.match(link):
        sys.exit("refocus: that is not a Brain link (it looks like https://.../brain/claim/...)")
    st, b = http("GET", link)
    if st != 200 or not b.get("key"):
        out("refocus: the link did not hand over a key: %s" % b.get("error", "HTTP %d" % st))
        sys.exit(5)
    os.makedirs(D, exist_ok=True)
    tmp = CONF + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"door": b["door"].rstrip("/"), "key": b["key"], "partner": b["partner"],
                   "connected": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)
    os.replace(tmp, CONF)
    try:
        os.chmod(CONF, 0o600)
    except OSError:
        pass
    w = door("GET", "/v1/whoami")
    out("CONNECTED  %s (%s, for %s)" % (w["partner"], w.get("kind", "partner"), w["person"]))
    out("  desk    %s" % ", ".join(w["desk"]))
    out("  key     stored in %s (this machine only; the link is now used up)" % CONF)


def cmd_whoami(a):
    c = conf() or stop_no_brain()
    w = door("GET", "/v1/whoami")
    out("REFOCUS whoami")
    out("  brain   %s (%s, for %s)" % (w["partner"], w.get("kind", "partner"), w["person"]))
    out("  desk    %s" % ", ".join(w["desk"]))
    out("  door    %s" % c["door"])
    out("  line    %s (from this folder's name; --line to choose another)" % default_line())
    out("  quiet   %s" % ("ON - do not ask about compacting" if os.path.exists(QUIET) else "off"))


def cmd_method(a):
    b = door("GET", "/v1/read?id=" + METHOD_ID)
    out("REFOCUS method  %s  (read live, %s)" % (b.get("name"), (b.get("modified") or "")[:10]))
    out("")
    out(b["text"])


def cmd_previous(a):
    line = line_of(a)
    ch = chain(line)
    out("REFOCUS previous  line %s" % line)
    if not ch:
        out("  NONE - this is the first CONTINUITY of the %s line. Say so in its frontmatter." % line)
    else:
        d, n, fid, name = ch[-1]
        b = door("GET", "/v1/read?id=" + fid)
        out("  LATEST  %s (%s)  %d chars" % (name, fid, len(b["text"])))
        out("")
        out(b["text"])
        out("")
    out("NEXT TITLE  %s" % next_title(line, ch))


def cmd_file(a):
    with open(a.content_file, encoding="utf-8", newline="") as f:
        body = f.read()
    if not body.strip():
        sys.exit("refocus: refusing to file an empty CONTINUITY")
    title = " ".join(a.title.split())
    m = TITLE_RX.match(title)
    if not m:
        sys.exit("refocus: title must be CONTINUITY-<LINE>-YYYY-MM-DD-NN (got %r)" % title)
    line = m.group(1)
    if a.line and a.line.upper() != line:
        sys.exit("refocus: --line %s does not match the title's line %s" % (a.line.upper(), line))
    if any(name == title for _, _, _, name in chain(line)):
        sys.exit("refocus: %s already exists - run `previous` again for the next title" % title)
    r = door("POST", "/v1/note", {"folder": "04_MEMORY", "title": title, "text": body, "kind": "continuity"})
    back = door("GET", "/v1/read?id=" + r["file_id"])
    mine = sha(back["text"])
    ok = r.get("verified") and not r.get("title_changed") and mine == r["readback_sha256"]
    out("REFOCUS file  %s" % r["title"])
    out("  FILEID    %s" % r["file_id"])
    out("  INTENDED  %s  %d bytes" % (r["intended_sha256"], r["bytes"]))
    out("  READBACK  %s  (door)" % r["readback_sha256"])
    out("  HERE      %s  (read again from this machine)" % mine)
    if r.get("title_changed"):
        out("  TITLE CHANGED on landing (%s) - a file of that name already existed" % r["title"])
    out("VERIFY %s" % ("PASS" if ok else "FAIL"))
    if not ok:
        out("  DO NOT CUT. The CONTINUITY is not on file as written; fix it before compacting.")
        sys.exit(4)
    # Only after VERIFY PASS do the older ones leave the live folder, never before the successor is safe.
    cutoff = (m.group(2), int(m.group(3)))
    old = [fid for d, n, fid, name in chain(line) if (d, n) < cutoff and fid != r["file_id"]]
    if not old:
        out("HISTORY  nothing older on the %s line" % line)
        return
    res = door("POST", "/v1/retire", {"folder": "04_MEMORY", "ids": old})
    bad = [x for x in res["moved"] if not x["ok"]]
    out("HISTORY  %d older CONTINUITY moved to 04_MEMORY/_HISTORY%s" % (len(old) - len(bad),
        "" if not bad else "; HISTORY FAIL for %d (the new one is filed and safe): %s" % (len(bad), bad)))


def cmd_cut(a):
    line = line_of(a)
    try:
        with open(HANDOFF, encoding="utf-8") as f:
            h = json.load(f)
    except (OSError, ValueError):
        h = {}
    key = os.path.normcase(os.path.abspath(os.getcwd()))
    h[key] = {"id": a.continuity_id, "name": a.name, "line": line, "at": time.time(),
              "cwd": os.path.abspath(os.getcwd())}
    os.makedirs(D, exist_ok=True)
    with open(HANDOFF + ".tmp", "w", encoding="utf-8") as f:
        json.dump(h, f, indent=1)
    os.replace(HANDOFF + ".tmp", HANDOFF)
    out("REFOCUS cut  %s (%s) on the %s line" % (a.name, a.continuity_id, line))
    out("NOT CUT - no tool can compact from inside a turn. Tell the person, in one line:")
    out('  "Filed and verified. Type /compact now - your conversation stays on screen."')
    out("After their /compact, this folder's hand-off points the new context at the CONTINUITY.")


def cmd_read(a):
    b = door("GET", "/v1/read?id=" + a.id)
    out("REFOCUS read  %s  (%s)" % (b.get("name"), b.get("why")))
    out("")
    out(b["text"])


def cmd_sweep(a):
    line = line_of(a)
    ch = chain(line)
    old = [(name, fid) for d, n, fid, name in ch[:-1]]
    out("REFOCUS sweep  line %s  %s" % (line, "APPLY" if a.apply else "DRY RUN (add --apply to move)"))
    out("  keep  %s" % (ch[-1][3] if ch else "nothing on this line"))
    for name, fid in old:
        out("  move  %s" % name)
    if a.apply and old:
        res = door("POST", "/v1/retire", {"folder": "04_MEMORY", "ids": [fid for _, fid in old]})
        out("  moved %d of %d" % (sum(1 for x in res["moved"] if x["ok"]), len(old)))


def cmd_quiet(a):
    if a.status:
        out("quiet is %s" % ("ON: the question is not asked on this machine" if os.path.exists(QUIET) else "off"))
        return
    if a.off:
        if os.path.exists(QUIET):
            os.remove(QUIET)
        out("quiet OFF - the question about compacting will be asked again when the window fills")
        return
    os.makedirs(D, exist_ok=True)
    with open(QUIET, "w", encoding="utf-8") as f:
        json.dump({"since": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)
    out("quiet ON - no more questions about compacting on this machine. Undo: 'ask me about compacting again'"
        " (refocus.py quiet --off)")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="refocus.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("connect")
    c.add_argument("link")
    sub.add_parser("whoami")
    sub.add_parser("method")
    p = sub.add_parser("previous")
    p.add_argument("--line")
    f = sub.add_parser("file")
    f.add_argument("--title", required=True)
    f.add_argument("--content-file", required=True)
    f.add_argument("--line", help="optional; the line is read from the title, and a mismatch is refused")
    k = sub.add_parser("cut")
    k.add_argument("--continuity-id", required=True)
    k.add_argument("--name", required=True)
    k.add_argument("--line")
    r = sub.add_parser("read")
    r.add_argument("id")
    s = sub.add_parser("sweep")
    s.add_argument("--line")
    s.add_argument("--apply", action="store_true")
    q = sub.add_parser("quiet")
    q.add_argument("--off", action="store_true")
    q.add_argument("--status", action="store_true")
    a = ap.parse_args()
    why = house_machine()
    if why:
        step_aside(why)
    {"connect": cmd_connect, "whoami": cmd_whoami, "method": cmd_method, "previous": cmd_previous,
     "file": cmd_file, "cut": cmd_cut, "read": cmd_read, "sweep": cmd_sweep, "quiet": cmd_quiet}[a.cmd](a)


if __name__ == "__main__":
    main()

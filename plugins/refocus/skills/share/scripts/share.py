# -*- coding: utf-8 -*-
"""share.py - the share rail: send what this Claude Code ran into to the J Flores house, and bring the answer back.

Omero, 2026-10-02, for Haru: "when he comes across things in his Claude Code, he can share them, and we can point
him in the right direction." Until then it was copy and paste over Telegram. A share lands in the Office room
help-<person>; Monday is called there and Omero reads it; the answer comes back here, and the refocus watch shows it
on the person's next message.

    share.py send --title T --file F      send it (F holds the text; --text "..." for a short one)
    share.py ask --need N --why W [--file F]   needs Omero's permission or access: Approve / Decline on his phone
    share.py replies [--all]              answers that came back since the last ones shown
    share.py thread [--n 20]              the last messages, both sides

Uses the key `refocus.py connect` stored. Standard library only.
Exit codes: 3 no brain connected - 4 sent but not read back the same - 5 the door refused - 6 the door did not answer.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
D = os.environ.get("REFOCUS_HOME") or os.path.join(HOME, ".claude", "refocus")   # REFOCUS_HOME: tests only
CONF = os.path.join(D, "door.json")
STATE = os.path.join(D, "share.json")


def out(s=""):
    sys.stdout.write(s + "\n")
    sys.stdout.flush()


def conf():
    try:
        with open(CONF, encoding="utf-8-sig") as f:
            c = json.load(f)
        if c.get("door") and c.get("key"):
            return c
    except (OSError, ValueError):
        pass
    out("NO BRAIN CONNECTED on this computer, so nothing was sent. The person needs their Brain link from Omero")
    out("(paste it and say 'connect my brain'). Until then, they can send Omero a picture of the screen.")
    sys.exit(3)


def door(method, path, body=None, timeout=60, quiet=False):
    c = conf()
    h = {"Accept": "application/json", "User-Agent": "refocus-plugin/share-1.0", "Authorization": "Bearer " + c["key"]}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(c["door"] + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8") or "{}").get("error")
        except ValueError:
            err = None
        if quiet:
            return None
        out("The Brain door refused: %s" % (err or "HTTP %d" % e.code))
        sys.exit(5)
    except Exception as e:
        if quiet:
            return None
        out("The Brain door did not answer (%s). Nothing was sent; try again in a minute." % type(e).__name__)
        sys.exit(6)


def state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(st):
    os.makedirs(D, exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f)
    os.replace(tmp, STATE)


def show(m):
    when = time.strftime("%a %b %d, %I:%M %p", time.localtime(m["ts"]))
    out("--- from %s, %s ---" % (m["from"], when))
    out(m["body"].rstrip())
    out("--- end ---")


def cmd_send(a):
    text = a.text
    if a.file:
        with open(a.file, encoding="utf-8") as f:
            text = f.read()
    if not (text or "").strip():
        sys.exit("share: nothing to send - give --file or --text")
    st = state()
    st.setdefault("seen", time.time() - 1)        # answers from now on are new; older ones were already handled
    r = door("POST", "/v1/share", {"title": a.title or "", "text": text})
    sent = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    if not r.get("verified"):
        out("SENT, but the house could not read it back the same (VERIFY FAIL, message %s). Say so to the person;"
            % r.get("id"))
        out("Omero may not have it whole.")
        sys.exit(4)
    st["last_share"] = time.time()
    st["room"] = r.get("room")
    save(st)
    out("SENT to the J Flores house - VERIFY PASS (room %s, message %s, text sha %s)." % (r["room"], r["id"], sent[:12]))
    if r.get("called"):
        out("Monday was called on it, and Omero reads that room too.")
    out("Their answer comes back here on its own: it shows on the person's next message after it arrives, or run")
    out("`share.py replies` when they ask whether anyone answered.")


def cmd_ask(a):
    """Omero 2026-10-02: anything that needs his permission or access goes to him as Approve / Decline on
    Telegram; his tap comes back here like any answer."""
    text = a.text or ""
    if a.file:
        with open(a.file, encoding="utf-8") as f:
            text = f.read()
    st = state()
    st.setdefault("seen", time.time() - 1)
    r = door("POST", "/v1/request", {"need": a.need, "why": a.why, "text": text})
    st["last_share"] = time.time()
    st["room"] = r.get("room")
    save(st)
    out("ASKED Omero - it is on his phone as Approve / Decline (ref %s, room %s, %s)." %
        (r["id"], r["room"], "VERIFY PASS" if r.get("verified") else "VERIFY FAIL"))
    out("His answer comes back here on its own, on the person's next message after he taps. If he approves, Monday")
    out("carries it out and says so in the same place.")


def cmd_replies(a):
    st = state()
    since = 0 if a.all else st.get("seen", 0)
    r = door("GET", "/v1/share/replies?since=%r" % float(since))
    msgs = r.get("messages") or []
    if not msgs:
        out("No answer yet from the J Flores house%s." % ("" if a.all else " since the last one shown"))
        return
    for m in msgs:
        show(m)
    st["seen"] = max(st.get("seen", 0), max(m["ts"] for m in msgs))
    save(st)


def cmd_thread(a):
    r = door("GET", "/v1/share?n=%d" % max(1, min(a.n, 200)))
    msgs = r.get("messages") or []
    if not msgs:
        out("Nothing has been shared from this computer yet.")
        return
    for m in msgs:
        show(dict(m, **{"from": "this computer" if m.get("mine") else m["from"]}))


def main():
    ap = argparse.ArgumentParser(description="the share rail: ask the J Flores house, get the answer back here")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send")
    s.add_argument("--title", default="")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--file")
    g.add_argument("--text")
    k = sub.add_parser("ask")
    k.add_argument("--need", required=True)
    k.add_argument("--why", required=True)
    g2 = k.add_mutually_exclusive_group()
    g2.add_argument("--file")
    g2.add_argument("--text")
    r = sub.add_parser("replies")
    r.add_argument("--all", action="store_true")
    t = sub.add_parser("thread")
    t.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    {"send": cmd_send, "ask": cmd_ask, "replies": cmd_replies, "thread": cmd_thread}[a.cmd](a)


if __name__ == "__main__":
    main()

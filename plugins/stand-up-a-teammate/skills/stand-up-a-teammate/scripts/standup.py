# -*- coding: utf-8 -*-
"""standup.py - begin a teammate's stand-up with Titus on the J Flores server, from this Claude Code.

Omero, 2026-10-28: "When someone stands someone up, it should be the skill that's used and the process begins."
A teammate of this house is formed by Titus and lives on the server. This script sends the person's words (and,
for a teammate that was already built on this computer, its files) to the house; it lands in the person's help room
in the Office with Titus called, and Titus's questions come back here the way share answers do.

    standup.py begin --words-file F [--name N]              a new teammate: the person's words, word for word
    standup.py home --name N --words-file F --attach P [P ...]   bring home a teammate built on this computer
    standup.py replies [--all]                              Titus's (and the house's) answers since the last shown
    standup.py preview --attach P [P ...]                   list what `home` would send, sending nothing

--attach takes files or folders. Folders are walked for text files (instructions, voice, code); .git, virtualenvs,
node_modules, caches, data and binaries are left out. A file holding what looks like a key is refused by the house.
Uses the key `refocus.py connect` stored. Standard library only.
Exit codes: 3 no brain connected - 4 sent but not read back the same - 5 the door refused - 6 the door did not answer
- 7 nothing to send.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
D = os.environ.get("REFOCUS_HOME") or os.path.join(HOME, ".claude", "refocus")   # REFOCUS_HOME: tests only
CONF = os.path.join(D, "door.json")
STATE = os.path.join(D, "share.json")          # the same state the share rail keeps: replies show on the next prompt
# Folders left on this computer, each named under "left here" with why. Every other folder is walked, dotted ones too:
# a Claude Code teammate keeps its persona in .claude/ (agents, commands, settings), and that is the part that must
# come home.
SKIP_DIRS = {".git": "version control", ".hg": "version control", ".svn": "version control",
             "node_modules": "installed packages", ".venv": "installed packages", "venv": "installed packages",
             "env": "installed packages", "__pycache__": "a cache", ".mypy_cache": "a cache", ".pytest_cache": "a cache",
             ".cache": "a cache", ".tmp": "scratch", "tmp": "scratch", "dist": "build output", "build": "build output",
             "data": "data (it stays here)", "logs": "logs", ".idea": "editor settings", ".vscode": "editor settings"}
TEXT_EXT = {".md", ".txt", ".py", ".js", ".ts", ".mjs", ".cjs", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
            ".sh", ".zsh", ".bash", ".ps1", ".cmd", ".bat", ".html", ".css", ".csv", ".sql", ".plist", ".service",
            ".timer", ".conf", ""}
SKIP_NAMES = {".env", ".env.local", ".DS_Store", "credentials.json", "token.json", "secrets.json"}
FILE_MAX = 200 * 1024
TOTAL_MAX = 400 * 1024
FILES_MAX = 40


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
    out("NO BRAIN CONNECTED on this computer, so the stand-up was NOT started, and nothing was built here.")
    out("Tell the person plainly: a teammate is formed by Titus on the J Flores server, and this computer has to be")
    out("connected to the house first. Omero sends a Brain link (paste it and say 'connect my brain'). Until then,")
    out("they can tell Monday on Telegram that they want to stand up a teammate. Do not build it here meanwhile.")
    sys.exit(3)


def door(method, path, body=None, timeout=90):
    c = conf()
    h = {"Accept": "application/json", "User-Agent": "house-plugin/standup-1.0", "Authorization": "Bearer " + c["key"]}
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
        if e.code == 404 and not err:
            err = "this door has no stand-up entrance yet (HTTP 404)"
        out("The house refused: %s" % (err or "HTTP %d" % e.code))
        out("Nothing was started. Tell the person what it said; if it is not something they can fix (a name, a")
        out("file to take out), send it to the house with the share skill. Do not build the teammate here instead.")
        sys.exit(5)
    except Exception as e:
        out("The house did not answer (%s). Nothing was started; try again in a minute. Do not build the teammate"
            % type(e).__name__)
        out("here instead.")
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


def read_words(a):
    with open(a.words_file, encoding="utf-8-sig") as f:
        w = f.read().strip()
    if not w:
        out("The words file is empty: write down what the person said they want, in their own words, and run again.")
        sys.exit(7)
    return w


def gather(paths):
    """[(relative path, text)] from files and folders; what was left out, with why."""
    got, left, total = [], [], 0

    def take(full, rel):
        nonlocal total
        if os.path.islink(full):                      # a link may point anywhere (~/.aws, an id_rsa): never follow it
            left.append((rel, "a link (only real files go)"))
            return
        name = os.path.basename(full)
        ext = os.path.splitext(name)[1].lower()
        if name in SKIP_NAMES or name.startswith(".env"):
            left.append((rel, "may hold secrets"))
            return
        if ext not in TEXT_EXT:
            left.append((rel, "not a text file"))
            return
        try:
            size = os.path.getsize(full)
        except OSError:
            left.append((rel, "could not be read"))
            return
        if size > FILE_MAX:
            left.append((rel, "larger than %d KB" % (FILE_MAX >> 10)))
            return
        try:
            with open(full, encoding="utf-8") as f:
                t = f.read()
        except (OSError, UnicodeDecodeError):
            left.append((rel, "not UTF-8 text"))
            return
        if len(got) >= FILES_MAX or total + len(t.encode("utf-8")) > TOTAL_MAX:
            left.append((rel, "over the %d files / %d KB a stand-up carries" % (FILES_MAX, TOTAL_MAX >> 10)))
            return
        total += len(t.encode("utf-8"))
        got.append((rel.replace("\\", "/"), t))

    for p in paths:
        p = os.path.abspath(os.path.expanduser(p))
        if os.path.isfile(p):
            take(p, os.path.basename(p))
        elif os.path.isdir(p):
            base = os.path.basename(p.rstrip("/\\")) or "files"
            for root, dirs, files in os.walk(p):
                for d in sorted(dirs):
                    drel = os.path.join(base, os.path.relpath(os.path.join(root, d), p)) + "/"
                    if os.path.islink(os.path.join(root, d)):
                        left.append((drel, "a link (only real folders are walked)"))
                    elif d in SKIP_DIRS:
                        left.append((drel, SKIP_DIRS[d]))
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not os.path.islink(os.path.join(root, d)))
                for fn in sorted(files):
                    full = os.path.join(root, fn)
                    take(full, os.path.join(base, os.path.relpath(full, p)))
        else:
            left.append((p, "not found"))
    return got, left


def show_gathered(got, left):
    for rel, t in got:
        out("  send  %s (%d bytes)" % (rel, len(t.encode("utf-8"))))
    for rel, why in left:
        out("  leave %s - %s" % (rel, why))


def started(r, what):
    st = state()
    st.setdefault("seen", time.time() - 1)
    st["last_share"] = time.time()
    st["room"] = r.get("room")
    save(st)
    if not r.get("verified"):
        out("SENT, but the house could not read it back the same (VERIFY FAIL, message %s). Tell the person; Titus"
            % r.get("id"))
        out("may not have it whole.")
        sys.exit(4)
    out("%s - VERIFY PASS (room %s, message %s). Titus was called on it." % (what, r["room"], r["id"]))
    if r.get("kept"):
        out("Its files are on the server now (%d, each read back), kept as %s." % (len(r.get("files") or []), r["kept"]))
    out("Titus's questions come back here on their own (on the person's next message), or run `standup.py replies`.")
    out("Answer him in the person's own words. Nothing of this teammate is built or run on this computer.")


def cmd_begin(a):
    r = door("POST", "/v1/standup", {"name": a.name or "", "words": read_words(a)})
    started(r, "STAND-UP STARTED with Titus on the J Flores server")


def cmd_home(a):
    got, left = gather(a.attach)
    if not got:
        out("Nothing to bring: no text files were found in what was given.")
        show_gathered(got, left)
        sys.exit(7)
    show_gathered(got, left)
    r = door("POST", "/v1/standup", {"name": a.name, "words": read_words(a), "existing": True,
                                     "files": [{"path": p, "text": t} for p, t in got]})
    started(r, "%s IS COMING HOME to the J Flores server" % a.name.upper())
    if left:
        out("Left on this computer (say so to the person; Titus may ask for some of it another way):")
        for rel, why in left:
            out("  %s - %s" % (rel, why))


def cmd_preview(a):
    got, left = gather(a.attach)
    show_gathered(got, left)
    out("%d file(s) would go, %d left here. Nothing was sent." % (len(got), len(left)))


def cmd_replies(a):
    st = state()
    since = 0 if a.all else st.get("seen", 0)
    r = door("GET", "/v1/share/replies?since=%r" % float(since))
    msgs = r.get("messages") or []
    if not msgs:
        out("No answer yet from Titus or the house%s." % ("" if a.all else " since the last one shown"))
        return
    for m in msgs:
        when = time.strftime("%a %b %d, %I:%M %p", time.localtime(m["ts"]))
        out("--- from %s, %s ---" % (m["from"], when))
        out(m["body"].rstrip())
        out("--- end ---")
    st["seen"] = max(st.get("seen", 0), max(m["ts"] for m in msgs))
    save(st)


def main():
    ap = argparse.ArgumentParser(description="begin a teammate's stand-up with Titus on the J Flores server")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("begin")
    b.add_argument("--words-file", required=True)
    b.add_argument("--name", default="")
    h = sub.add_parser("home")
    h.add_argument("--name", required=True)
    h.add_argument("--words-file", required=True)
    h.add_argument("--attach", nargs="+", required=True)
    p = sub.add_parser("preview")
    p.add_argument("--attach", nargs="+", required=True)
    r = sub.add_parser("replies")
    r.add_argument("--all", action="store_true")
    a = ap.parse_args()
    {"begin": cmd_begin, "home": cmd_home, "preview": cmd_preview, "replies": cmd_replies}[a.cmd](a)


if __name__ == "__main__":
    main()

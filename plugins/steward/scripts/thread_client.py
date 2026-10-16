# -*- coding: utf-8 -*-
"""THE LAPTOP HALF OF A STEWARD'S ONE THREAD (2026-10-15, w-d722be54).

DECISION-ONE-THREAD-FOR-EVERY-TEAMMATE-2026-10-15-01, step 2: a person's laptop Claude Code (once landed, this
Claude Code IS the steward's body - IDENTITY-MONDAY, 2026-09-24) and their steward's server seat keep ONE thread,
the sealed room steward_door.py serves on the server side. Shaped on Monday's own bench hook (one_thread.py): the
same idempotent client-id posting and local outbox/session-state pattern, but HTTP+Bearer to steward_door.py's
/thread instead of Monday's SSH transport - and, unlike that bench hook's single combined call, POST and GET are
two separate requests here, handled independently: a redundant re-POST after a read failure is always safe (the
door's own ledger drops a client id it has already seen), so nothing is lost by retrying both next time.

  on_prompt   the person's own typed words go into the room as a "bench" line (wakes no one, reaches no phone),
              and whatever is new there since this session last looked comes back as context: their steward's
              Telegram side, another laptop session.
  on_stop     this session's final reply - generated locally, by the landed steward - goes there too, in the
              background, so the turn ends at once.
  flush       the background half of on_stop, run as a detached subprocess of this same file.

Local state lives under ~/.claude/steward/thread/ - the connection (base, token, person, steward) is written by
`steward.py thread-connect <claim-link>` to ~/.claude/steward/thread.json, deliberately separate from
~/.claude/refocus/door.json: that one is the Brain-formation key, a different door and a different security
domain. No thread.json yet means every function below no-ops silently, so nothing breaks for anyone who has
never connected this laptop's thread half. STEWARD_THREAD=off is the emergency kill switch.

The log holds counts and durations, never words.
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

HOME = os.path.expanduser("~")
SD = os.environ.get("STEWARD_HOME") or os.path.join(HOME, ".claude", "steward")
CONF = os.path.join(SD, "thread.json")
DIR = os.path.join(SD, "thread")
OUTBOX = os.path.join(DIR, "outbox")
SESSIONS = os.path.join(DIR, "sessions")
LOG = os.path.join(DIR, "thread_client.log")

HIS_MAX = 4000              # a person's own prompt, cut here before it is queued
MINE_MAX = 5000             # the steward's reply, cut here before it is queued
SHOW_MAX = 15               # lines rendered back into context on an ordinary prompt
SHOW_BODY = 700             # a shown line's body, cut here
FIRST_SHOW = 8              # lines rendered on the very first prompt a session ever makes
FIRST_LOOK_S = 12 * 3600    # how far back the very first read reaches
POST_MAX = 20               # outbox items flushed in one call
HTTP_TIMEOUT = 15
FLUSH_TIMEOUT = 45

TAG_RE = re.compile(r"^\(On the laptop, [^)]*?session ([0-9a-f]{8})\) ?")
NOT_HIS = re.compile(r"^\s*<")              # a tool-generated prompt (e.g. a slash command's own echo), not a person's

HTTP = None                  # fn(method, url, token, body, timeout) -> (status, dict); a test hands in its own


def log(what):
    try:
        os.makedirs(DIR, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), what))
    except OSError:
        pass


def conf():
    if os.environ.get("STEWARD_THREAD") == "off":
        return None
    try:
        with io.open(CONF, encoding="utf-8") as f:
            c = json.load(f)
        if c.get("base") and c.get("token") and c.get("person") and c.get("steward"):
            return c
    except (OSError, ValueError):
        pass
    return None


def _steward_name(c):
    return c["steward"].split("-")[-1].capitalize()


def tag(sid):
    return "(On the laptop, %s, session %s) " % (time.strftime("%H:%M"), sid[:8])


def cut(text, n):
    text = text.strip()
    return text if len(text) <= n else text[:n].rstrip() + "\n(...cut here; %d chars on the laptop)" % len(text)


# ---------------------------------------------------------------- per-session read cursor
def _state_path(sid):
    return os.path.join(SESSIONS, "%s.json" % re.sub(r"[^A-Za-z0-9_-]", "", sid)[:80])


def load(sid):
    try:
        with io.open(_state_path(sid), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(sid, st):
    os.makedirs(SESSIONS, exist_ok=True)
    path = _state_path(sid)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f)
    os.replace(tmp, path)


# ---------------------------------------------------------------- the outbox: one file per queued line
def _box(sid):
    return os.path.join(OUTBOX, re.sub(r"[^A-Za-z0-9_-]", "", sid)[:80])


def queue(sid, who, text):
    cid = "%s-%s" % (sid[:8], uuid.uuid4().hex[:16])
    box = _box(sid)
    os.makedirs(box, exist_ok=True)
    path = os.path.join(box, "%d-%s.json" % (time.time_ns(), cid))
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump({"id": cid, "who": who, "text": text}, f)
    os.replace(tmp, path)
    return cid


def waiting(sid):
    try:
        names = sorted(n for n in os.listdir(_box(sid)) if n.endswith(".json"))
    except OSError:
        return []
    out = []
    for n in names:
        path = os.path.join(_box(sid), n)
        try:
            with io.open(path, encoding="utf-8") as f:
                out.append((path, json.load(f)))
        except (OSError, ValueError):
            continue
    return out


def settle(items, posted):
    done = {p.get("id") for p in (posted or []) if p.get("ok")}
    n = 0
    for path, it in items:
        if it.get("id") in done:
            try:
                os.remove(path)
                n += 1
            except OSError:
                pass
    return n


# ---------------------------------------------------------------- the door, two calls, never one
def _http(method, url, token, body=None, timeout=HTTP_TIMEOUT):
    if HTTP is not None:
        return HTTP(method, url, token, body, timeout)
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8") if body is not None else None,
                                 method=method)
    req.add_header("authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except ValueError:
            return e.code, {}


def post(c, items, timeout=HTTP_TIMEOUT):
    return _http("POST", c["base"].rstrip("/") + "/thread", c["token"], {"posts": items}, timeout)


def read(c, since, limit=60):
    url = "%s/thread?since=%r&limit=%d" % (c["base"].rstrip("/"), since, limit)
    return _http("GET", url, c["token"])


# ---------------------------------------------------------------- what the person sees
def label(line, c):
    body = line.get("body") or ""
    author = line.get("author_id")
    if line.get("kind") == "bench":
        m = TAG_RE.match(body)
        where = "on the laptop (session %s)" % (m.group(1) if m else "?")
        body = body[m.end():] if m else body
        who = ("you" if author == c["person"] else (line.get("name") or author)) + ", " + where
    else:
        who = "you" if author == c["person"] else (line.get("name") or author or "?")
    body = re.sub(r"\s+", " ", body).strip()
    if len(body) > SHOW_BODY:
        body = body[:SHOW_BODY].rstrip() + " (...)"
    return who, body


def render(lines, first, c):
    if not lines:
        return ""
    shown = lines[-(FIRST_SHOW if first else SHOW_MAX):]
    name = _steward_name(c)
    head = (("THE ONE THREAD - the last 12 hours in your room with %s:" % name) if first else
            ("THE ONE THREAD - new in your room with %s since this session last looked:" % name))
    out = [head]
    for line in shown:
        who, body = label(line, c)
        out.append("- %s %s: %s" % (time.strftime("%H:%M", time.localtime(line.get("ts") or 0)), who, body))
    if len(lines) > len(shown):
        out.append("(%d earlier line(s) not shown.)" % (len(lines) - len(shown)))
    out.append("(This is the same room reachable from %s's Telegram. Nothing here is addressed to this session "
                "alone.)" % name)
    return "\n".join(out)


# ---------------------------------------------------------------- the hooks
def on_prompt(ev):
    c = conf()
    if not c:
        return ""
    sid = ev.get("session_id") or ""
    if not sid:
        return ""
    sid8 = sid[:8]
    st = load(sid)
    prompt = ev.get("prompt") if isinstance(ev.get("prompt"), str) else ""
    st["open"] = None
    if prompt.strip() and not NOT_HIS.match(prompt):
        st["open"] = queue(sid, "person", tag(sid) + cut(prompt, HIS_MAX))
    first = st.get("seen") is None
    items = waiting(sid)[:POST_MAX]
    notes, posted = [], 0
    try:
        if items:
            pst, pout = post(c, [it for _, it in items])
            if pst >= 400:
                raise RuntimeError("POST HTTP %d" % pst)
            posted = settle(items, pout.get("posted"))
    except Exception as e:
        n = len(waiting(sid))
        log("prompt %s post FAILED (%d waiting): %s" % (sid8, n, str(e)[:200]))
        notes.append("[steward] Could not reach your room with %s right now (%s). %d line(s) from this laptop "
                     "wait here and go with the next call." % (_steward_name(c), str(e)[:160], n))
    shown = ""
    try:
        rst, rout = read(c, st.get("seen") if st.get("seen") is not None else (time.time() - FIRST_LOOK_S))
        if rst >= 400:
            raise RuntimeError("GET HTTP %d" % rst)
        st["seen"] = rout.get("newest") if rout.get("newest") is not None else (st.get("seen") or time.time())
        lines = [l for l in (rout.get("lines") or [])
                 if not (TAG_RE.match(l.get("body") or "") and TAG_RE.match(l["body"]).group(1) == sid8)]
        log("prompt %s posted %d, %d new there, %d shown" % (sid8, posted, rout.get("total_new") or 0, len(lines)))
        shown = render(lines, first, c)
    except Exception as e:
        log("prompt %s read FAILED: %s" % (sid8, str(e)[:200]))
        if not notes:
            notes.append("[steward] Could not read your room with %s right now (%s)."
                         % (_steward_name(c), str(e)[:160]))
    save(sid, st)
    return "\n".join(n for n in (notes + [shown]) if n)


def on_stop(ev, reply_text):
    c = conf()
    if not c:
        return
    sid = ev.get("session_id") or ""
    if not sid:
        return
    st = load(sid)
    if not st.get("open"):
        return                 # this turn's prompt was never synced (empty, a tool echo, or no connection then)
    st["open"] = None
    save(sid, st)
    text = reply_text if isinstance(reply_text, str) else ""
    if not text.strip():
        log("stop %s: no final words to carry over" % sid[:8])
        return
    queue(sid, "steward", tag(sid) + cut(text, MINE_MAX))
    spawn_flush(sid)


def flush(sid):
    c = conf()
    if not c:
        return
    items = waiting(sid)[:POST_MAX]
    if not items:
        return
    try:
        pst, pout = post(c, [it for _, it in items], timeout=FLUSH_TIMEOUT)
        if pst >= 400:
            raise RuntimeError("HTTP %d" % pst)
    except Exception as e:
        log("flush %s FAILED (%d waiting): %s" % (sid[:8], len(items), str(e)[:200]))
        return
    log("flush %s posted %d of %d" % (sid[:8], settle(items, pout.get("posted")), len(items)))


def spawn_flush(sid):
    """A detached process so on_stop returns at once; the network round trip happens after the turn ends."""
    args = [sys.executable, os.path.abspath(__file__), "flush", sid]
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    if os.name != "nt":
        subprocess.Popen(args, start_new_session=True, **kw)
        return
    flags = 0x00000008 | 0x00000200          # CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    try:
        subprocess.Popen(args, creationflags=flags | 0x01000000, **kw)   # | CREATE_BREAKAWAY_FROM_JOB
    except OSError:
        subprocess.Popen(args, creationflags=flags, **kw)


def main(argv):
    if len(argv) > 1 and argv[1] == "flush":
        flush(argv[2] if len(argv) > 2 else "")


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as e:
        log("crash %s: %s" % (type(e).__name__, str(e)[:200]))

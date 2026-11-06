# -*- coding: utf-8 -*-
# Stop - after every reply, this session's new work goes to the J Flores server, where the house can read it.
#
# Omero, 2026-11-06: "I need to know what Marc and Gidion are working on. And if we can not see then we need to write
# the program that insures all work being done on computers in our team get transferred to the server where we can
# read." Until this, a laptop reached the house only when its person chose to share, so twice in two days Crystal's
# live code changed from a laptop with no record of what or why.
#
# What goes: the new lines of this session's transcript since the last send - what the person asked, what Claude
# answered, every tool call (files edited, commands run) and a cut of each result. It goes to POST /v1/worklog on the
# Brain door, under this computer's own door key, and the server stores it per person, per day, per session, with
# keys, tokens, passwords and card numbers masked. The offset moves only on a 200, so nothing is lost offline: the
# next reply (or the next session's start, `sweep`) sends what is still waiting.
#
# What never goes: a session that touched a Faithful Steward's PERSON side (the interview, a private note). The
# session is marked private here and nothing more of it is sent. Every unsent line is checked before any of them
# goes, so a session that opens with the interview sends nothing at all.
#
# The person is told once, plainly, by hello.py. The hook itself returns at once: the send runs detached, after the
# turn ends. Its log holds counts, never words. REFOCUS_WORKLOG=off is the kill switch.
import calendar
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
D = os.environ.get("REFOCUS_HOME") or os.path.join(HOME, ".claude", "refocus")   # REFOCUS_HOME: tests only
CONF = os.path.join(D, "door.json")
W = os.path.join(D, "worklog")
LOG = os.path.join(W, "worklog.log")
CLIENT = "refocus-worklog/1.0"

BATCH_ENTRIES = 300
BATCH_BYTES = 350 * 1024       # the door takes 512 KB a body
BATCHES_PER_RUN = 30
CUT = {"ask": 20000, "answer": 20000, "tool": 8000, "result": 2000}
HTTP_TIMEOUT = 30
PRIVATE_RX = re.compile(r"steward\.py\s+(?:start|brief|draft|ratify|finish|pause)\b|--side[ =]person\b|"
                        r"\"side\"\s*:\s*\"person\"|/steward:start\b")
HTTP = None                    # fn(url, key, body) -> (status, dict); a test hands in its own


def log(what):
    try:
        os.makedirs(W, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8", newline="") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), what))
    except OSError:
        pass


def house_machine():
    if os.environ.get("REFOCUS_IGNORE_HOUSE_WATCH"):
        return False                                   # tests only
    return bool(os.environ.get("OFFICE_SEAT")
                or os.path.exists(os.path.join(HOME, ".claude", "hooks", "context_watch.py"))
                or os.path.exists(os.path.join(HOME, ".claude", "brain.json"))
                or os.path.isdir("/home/monday/office"))


def conf():
    if os.environ.get("REFOCUS_WORKLOG", "").lower() == "off" or house_machine():
        return None
    try:
        with io.open(CONF, encoding="utf-8-sig") as f:
            c = json.load(f)
    except Exception:
        return None
    return c if c.get("door") and c.get("key") else None


def _state_path(sid):
    return os.path.join(W, "sessions", re.sub(r"[^A-Za-z0-9-]", "", sid)[:64] + ".json")


def load(sid):
    try:
        with io.open(_state_path(sid), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"offset": 0, "line": 0, "private": False}


def save(sid, st):
    p = _state_path(sid)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(st, f)
    os.replace(tmp, p)


# ---------------------------------------------------------------- the transcript, read as entries
def _text(content):
    if isinstance(content, str):
        return content
    out = []
    for c in content or []:
        if isinstance(c, dict):
            if c.get("type") == "text":
                out.append(c.get("text") or "")
            elif c.get("type") == "tool_result":
                out.append(_text(c.get("content")))
    return "\n".join(x for x in out if x)


def entries_of(rec, i):
    """One transcript record -> the entries it holds (thinking and housekeeping records give none)."""
    if rec.get("type") not in ("user", "assistant"):
        return []
    try:
        ts = float(calendar.timegm(time.strptime((rec.get("timestamp") or "")[:19], "%Y-%m-%dT%H:%M:%S")))
    except ValueError:
        ts = time.time()                                # transcripts stamp UTC ("...Z"); none means now
    msg = rec.get("message") or {}
    content = msg.get("content")
    out = []
    if rec.get("type") == "user":
        if isinstance(content, str):
            if content.strip():
                out.append({"kind": "ask", "text": content[:CUT["ask"]]})
        else:
            for c in content or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text" and (c.get("text") or "").strip():
                    out.append({"kind": "ask", "text": c["text"][:CUT["ask"]]})
                elif c.get("type") == "tool_result":
                    out.append({"kind": "result", "text": _text(c.get("content"))[:CUT["result"]]})
    else:
        for c in content or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text" and (c.get("text") or "").strip():
                out.append({"kind": "answer", "text": c["text"][:CUT["answer"]]})
            elif c.get("type") == "tool_use":
                out.append({"kind": "tool", "tool": str(c.get("name") or "")[:60],
                            "text": json.dumps(c.get("input") or {}, ensure_ascii=False)[:CUT["tool"]]})
    for e in out:
        e["i"], e["ts"] = i, ts
    return out


def read_new(tp, st):
    """The complete lines after the stored offset: (entries, new offset, new line count, private seen)."""
    with io.open(tp, "rb") as f:
        f.seek(st["offset"])
        data = f.read()
    end = data.rfind(b"\n")
    if end < 0:
        return [], st["offset"], st["line"], False
    entries, line, private = [], st["line"], False
    for raw in data[:end].split(b"\n"):
        line += 1
        try:
            rec = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            continue
        for e in entries_of(rec, line):
            if PRIVATE_RX.search(e["text"]):
                private = True
            entries.append(e)
    return entries, st["offset"] + end + 1, line, private


# ---------------------------------------------------------------- the send
def _post(c, body):
    if HTTP is not None:
        return HTTP(c["door"].rstrip("/") + "/v1/worklog", c["key"], body)
    req = urllib.request.Request(c["door"].rstrip("/") + "/v1/worklog", method="POST",
                                 data=json.dumps(body, ensure_ascii=False).encode("utf-8"))
    req.add_header("Authorization", "Bearer " + c["key"])
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", CLIENT)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except ValueError:
            return e.code, {}


def batches(entries):
    cur, size = [], 0
    for e in entries:
        n = len(json.dumps(e, ensure_ascii=False).encode("utf-8"))
        if cur and (len(cur) >= BATCH_ENTRIES or size + n > BATCH_BYTES):
            yield cur
            cur, size = [], 0
        cur.append(e)
        size += n
    if cur:
        yield cur


def flush(sid, tp, cwd=""):
    """Send what this session has waiting. Returns the number of entries the server stored."""
    c = conf()
    if not c or not sid or not tp or not os.path.exists(tp):
        return 0
    st = load(sid)
    st["tp"], st["cwd"] = tp, cwd or st.get("cwd", "")
    if st.get("private"):
        return 0
    stored = 0
    for _ in range(BATCHES_PER_RUN):
        entries, off, line, private = read_new(tp, st)
        if private:
            st["private"] = True
            save(sid, st)
            log("session %s touched a person side: marked private, nothing sent" % sid[:8])
            return stored
        if off == st["offset"]:
            break
        if not entries:                                 # only housekeeping lines: move past them
            st["offset"], st["line"] = off, line
            save(sid, st)
            continue
        # send at most one batch per pass, then move the offset only as far as that batch reached
        first = next(batches(entries))
        upto = first[-1]["i"]
        body = {"session": sid, "cwd": st["cwd"], "host": socket.gethostname()[:80], "client": CLIENT,
                "entries": first}
        try:
            code, out = _post(c, body)
        except Exception as e:
            log("send %s FAILED: %s" % (sid[:8], str(e)[:160]))
            return stored
        if code != 200:
            log("send %s refused HTTP %d: %s" % (sid[:8], code, str((out or {}).get("error"))[:160]))
            return stored
        stored += int((out or {}).get("stored") or 0)
        if upto >= line:
            st["offset"], st["line"] = off, line
        else:
            st["offset"], st["line"] = _offset_of_line(tp, st, upto), upto
        save(sid, st)
    log("send %s stored %d" % (sid[:8], stored))
    return stored


def _offset_of_line(tp, st, line_no):
    """The byte offset just after transcript line `line_no`, counting from the stored offset."""
    with io.open(tp, "rb") as f:
        f.seek(st["offset"])
        off, line = st["offset"], st["line"]
        for raw in f:
            if line >= line_no:
                break
            off += len(raw)
            line += 1
    return off


def sweep():
    """Every session with something still waiting (an offline laptop, a closed window): send it."""
    sd = os.path.join(W, "sessions")
    if not conf() or not os.path.isdir(sd):
        return
    for name in sorted(os.listdir(sd)):
        if not name.endswith(".json"):
            continue
        st = load(name[:-5])
        tp = st.get("tp") or ""
        if st.get("private") or not tp or not os.path.exists(tp) or os.path.getsize(tp) <= st.get("offset", 0):
            continue
        flush(name[:-5], tp, st.get("cwd", ""))


def spawn(*args):
    """Detached, so the hook returns at once and the send happens after the turn ends."""
    argv = [sys.executable, os.path.abspath(__file__)] + list(args)
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    if os.name != "nt":
        subprocess.Popen(argv, start_new_session=True, **kw)
        return
    flags = 0x00000008 | 0x00000200          # CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    try:
        subprocess.Popen(argv, creationflags=flags | 0x01000000, **kw)   # | CREATE_BREAKAWAY_FROM_JOB
    except OSError:
        subprocess.Popen(argv, creationflags=flags, **kw)


def main(argv):
    if len(argv) > 1 and argv[1] == "flush":
        flush(argv[2], argv[3], argv[4] if len(argv) > 4 else "")
        return
    if len(argv) > 1 and argv[1] == "sweep":
        sweep()
        return
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")      # Windows hands hooks cp1252 otherwise
    ev = json.loads(raw or "{}")
    if conf() and ev.get("session_id") and ev.get("transcript_path"):
        spawn("flush", ev["session_id"], ev["transcript_path"], ev.get("cwd") or "")


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as e:
        log("crash %s: %s" % (type(e).__name__, str(e)[:200]))
    sys.exit(0)

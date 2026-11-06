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
# Brain door, under this computer's own door key. Keys, tokens, passwords, cookies and card numbers are masked HERE,
# on the whole text, before anything is cut or sent (the door's own nets, copied below, plus the extra nets); the
# server masks again and seals the words so only Omero's root and Monday can read them. The offset moves only on a
# 200 and only past whole transcript records, so nothing is lost offline and nothing is cut in half: the next reply
# (or the next session's start, `sweep`) sends what is still waiting.
#
# What never goes: anything after the person says "off the record", and a session that touched a Faithful
# Steward's PERSON side (the interview, a private note). The
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
OFF_RECORD_RX = re.compile(r"\boff[\s_-]+(?:the[\s_-]+)?record\b", re.I)
MASK = "[masked]"
HTTP = None                    # fn(url, key, body) -> (status, dict); a test hands in its own


# ---------------------------------------------------------------- the door's nets (a copy of brain_door.py's own)
# Masking starts here, before anything leaves this computer (Nathan and Shallum, 11-06: the r1 laptop sent raw text).
# This block is byte-for-byte the brain door's SECRET_SHAPE_RX ... _keyish; the server's test checks it still is.
SECRET_SHAPE_RX = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{8,}|\bsk-[A-Za-z0-9_-]{16,}|\b[sr]k_(?:live|test)_[A-Za-z0-9]{8,}|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}|\bxox[abprs]-[A-Za-z0-9-]{10,}|"
    r"\bAKIA[0-9A-Z]{16}\b|\bAIza[0-9A-Za-z_-]{30,}|\bya29\.[0-9A-Za-z_-]{20,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY|\bbd_[A-Za-z0-9_-]{20,}|"
    r"\b(?i:bearer)\s+[A-Za-z0-9._~+/=-]{16,}|\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|"
    r"\b[a-z][a-z0-9+.-]{1,20}://[^\s/:@'\"]+:[^\s/@'\"]{3,}@|"
    # a Telegram bot token, bare or inside an api.telegram.org/bot<token>/ URL (this house runs on Telegram)
    r"(?<!\d)\d{8,10}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])|"
    r"hooks\.slack\.com/(?:services|workflows|triggers)/[A-Za-z0-9_/-]{16,})")
# 2. a value given to a name that says secret (HCP_API_KEY=..., "password": "...", token: '...'), when the value looks
#    like a key and not like prose or code that reads a key from somewhere else;
SECRET_LABEL_RX = re.compile(
    r"""(?i)(?<![A-Za-z0-9_.-])["']?[A-Za-z0-9_.-]{0,40}?(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|"""
    r"""access[_-]?key|private[_-]?key|client[_-]?secret|auth)[A-Za-z0-9_.-]{0,40}["']?[ \t]*[:=][ \t]*"""
    r"""(?P<v>"[^"\n]{0,400}"|'[^'\n]{0,400}'|[^\s,;#]{1,400})""")   # bounded: a 200 KB line can't stall the door
SECRET_LOOKUP_RX = re.compile(r"^(?:os\.|process\.env|getenv|env\[|load|read|get_|fetch|vault|keyring|secrets\.|\$)",
                              re.I)
# 3. a payment card number (13-19 digits, spaces or dashes allowed, Luhn-valid, a card network's first digit).
CARD_RX = re.compile(r"(?<![\d-])[2-6](?:[ -]?\d){12,18}(?![\d-])")


def _luhn(digits):
    s, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        s += d
        alt = not alt
    return s % 10 == 0


def _not_a_key(v):
    """A path, a URL or a slug of words (rocket-hcp-key-2025) names where a key is, it is not one. Only what LOOKS
    like a path counts: a leading / ~/ ./ ../ .../, a ://, or every / segment lowercase. Many keys hold a "/"
    (wJalrXUtnFEMI/K7MDENG/..., k8s/prod/Abc123...): mixed-case or digit-heavy segments stay keys (Shallum, 10-28)."""
    if re.match(r"(?:/|~/|\./|\.\./|\.\.\./)", v) or "://" in v:
        return True
    if "/" in v and all(re.fullmatch(r"[a-z0-9._-]+", s) for s in v.split("/") if s):
        return True
    return re.fullmatch(r"[a-z]+(?:-[a-z0-9]{1,12}){2,}", v) is not None


def _keyish(v):
    """A value that looks like a key: one run of 12+ key characters with letters and digits, not a sentence."""
    return (len(v) >= 12 and not re.search(r"\s", v) and re.search(r"[A-Za-z]", v) is not None and
            re.search(r"\d", v) is not None and re.fullmatch(r"[A-Za-z0-9_+/=.~!@#$%^&*:-]+", v) is not None and
            not _not_a_key(v))
# ---------------------------------------------------------------- end of the door's nets


# ---------------------------------------------------------------- the extra nets (one text, two copies)
# The door's nets catch key SHAPES and long labelled values. A work session also prints what they miss (Nathan and
# Shallum's review of worklog-1106, 11-06): a cookie header, a short password after a label, a login in a command line.
# This block is identical in the laptop's worklog.py and the server's worklog.py; test_worklog.py checks they match.
# What no net here can see, said plainly: a password typed as a sentence ("the password is ..."), a key with no
# shape and no label, a secret inside a file path, and an id number. Over-masked on purpose: a 13-19 digit number
# that passes the card check, even when it was an order id.
EXTRA_RX = [
    # Cookie: a=b; c=d  /  set-cookie: x=y   -> the whole header value
    re.compile(r"(?im)(\b(?:set-)?cookie\s*[:=]\s*)([^\n]+)"),
    # curl -u user:pass, curl --user user:pass
    re.compile(r"(?i)(\s(?:-u|--user)\s*['\"]?[^\s'\":]+:)([^\s'\"]+)"),
    # mysql -pSecret / mysqldump -p'Secret'
    re.compile(r"(?i)(\bmysql(?:dump|admin)?\b[^\n]*?\s-p)(['\"]?[^\s'\"]+['\"]?)"),
    # sshpass -p secret
    re.compile(r"(?i)(\bsshpass\s+-p\s*)(['\"]?[^\s'\"]+['\"]?)"),
    # a short value after a secret's label: password=hunter2, session_id: abc123, PGPASSWORD=x9
    re.compile(r"(?i)((?<![A-Za-z0-9_])[A-Za-z0-9_.-]{0,30}?(?:password|passwd|pwd|secret|token|api[_-]?key|"
               r"session[_-]?id|sessionid|session|cookie|auth)[A-Za-z0-9_.-]{0,20}[ \t]*[:=][ \t]*)"
               r"(['\"]?)([^\s'\",;#)]{4,200})(\2)"),
]


def _extra_value_is_secret(v):
    """A labelled short value is masked unless it plainly is code or prose: a call, a lookup, a word, a None."""
    if "(" in v or v.lower() in ("none", "null", "true", "false", "undefined", "str", "string", "bytes", "int"):
        return False
    if re.match(r"(?:os\.|process\.env|getenv|env\[|self\.|\$\{?|<|\{\{)", v):
        return False
    return bool(re.search(r"[\d\W_]", v)) or len(v) >= 16


PRIVATE_KEY_BLOCK_RX = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)")
AUTH_HEADER_RX = re.compile(r"(?i)(\bauthorization\s*[:=]\s*(?:(?:token|basic|bearer|digest|apikey|key)\s+)?)"
                            r"([^\s'\",;]{6,})")


def mask_first(t):
    """Before the door's nets: a private key's whole block (the door's net masks only its BEGIN line, Nathan 11-06),
    and any Authorization header's value, whatever its scheme (HCP's API uses `Token <key>`)."""
    return AUTH_HEADER_RX.sub(lambda m: m.group(1) + MASK, PRIVATE_KEY_BLOCK_RX.sub(MASK, t))


def mask_extra(t):
    out = EXTRA_RX[0].sub(lambda m: m.group(1) + MASK, t)
    for rx in EXTRA_RX[1:4]:
        out = rx.sub(lambda m: m.group(1) + MASK, out)
    return EXTRA_RX[4].sub(lambda m: (m.group(1) + m.group(2) + MASK + m.group(4))
                           if _extra_value_is_secret(m.group(3)) else m.group(0), out)
# ---------------------------------------------------------------- end of the extra nets


def mask(text):
    """The door's nets, then the extra nets. Called on the whole text, before any cut, so no half key survives."""
    t = SECRET_SHAPE_RX.sub(MASK, mask_first(text or ""))

    def lab(m):
        v = m.group("v")
        bare = v[1:-1] if v[:1] in "\"'" and v[-1:] == v[:1] and len(v) > 1 else v
        if _keyish(bare) or (v[:1] in "\"'" and len(bare) >= 6 and " " not in bare):
            return m.group(0)[:m.start("v") - m.start(0)] + MASK
        return m.group(0)

    def cc(m):
        d = re.sub(r"\D", "", m.group(0))
        return MASK if 13 <= len(d) <= 19 and _luhn(d) else m.group(0)
    return mask_extra(CARD_RX.sub(cc, SECRET_LABEL_RX.sub(lab, t)))


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
        return {"offset": 0, "line": 0, "skip_j": 0, "private": False}


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
                out.append({"kind": "ask", "text": content})
        else:
            for c in content or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text" and (c.get("text") or "").strip():
                    out.append({"kind": "ask", "text": c["text"]})
                elif c.get("type") == "tool_result":
                    out.append({"kind": "result", "text": _text(c.get("content"))})
    else:
        for c in content or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text" and (c.get("text") or "").strip():
                out.append({"kind": "answer", "text": c["text"]})
            elif c.get("type") == "tool_use":
                out.append({"kind": "tool", "tool": str(c.get("name") or "")[:60],
                            "text": json.dumps(c.get("input") or {}, ensure_ascii=False)})
    for j, e in enumerate(out):
        e["private"] = bool(PRIVATE_RX.search(e["text"]) or (e["kind"] == "ask" and OFF_RECORD_RX.search(e["text"])))
        e["text"] = mask(e["text"])[:CUT[e["kind"]]]                 # mask the whole text first, then cut
        e["i"], e["j"], e["ts"] = i, j, ts
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
            private = private or e.pop("private")
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


def _size(e):
    return len(json.dumps(e, ensure_ascii=False).encode("utf-8"))


def pick_batch(entries):
    """The next batch, cut only between transcript records (Nathan and Shallum, 11-06: an r1 batch cut through a
    record and its tail was never sent). A single record too big for one batch goes in pieces; the state then
    remembers how far into it the server has it (skip_j)."""
    recs = {}
    for e in entries:
        recs.setdefault(e["i"], []).append(e)
    batch, size = [], 0
    for es in recs.values():
        rs = sum(_size(e) for e in es)
        if not batch and (len(es) > BATCH_ENTRIES or rs > BATCH_BYTES):
            for e in es:
                n = _size(e)
                if batch and (len(batch) >= BATCH_ENTRIES or size + n > BATCH_BYTES):
                    break
                batch.append(e)
                size += n
            break
        if batch and (len(batch) + len(es) > BATCH_ENTRIES or size + rs > BATCH_BYTES):
            break
        batch += es
        size += rs
    last = batch[-1]
    return batch, last["j"] == recs[last["i"]][-1]["j"]


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
        skip = st.get("skip_j", 0)
        entries = [e for e in entries if not (e["i"] == st["line"] + 1 and e["j"] < skip)]
        if not entries:                                 # the rest of a split record was all sent
            st["offset"], st["line"], st["skip_j"] = _offset_of_line(tp, st, st["line"] + 1), st["line"] + 1, 0
            save(sid, st)
            continue
        # send one batch per pass, then move the offset only as far as that batch reached
        first, whole = pick_batch(entries)
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
        if whole:
            st["offset"], st["line"], st["skip_j"] = _offset_of_line(tp, st, upto), upto, 0
        else:                                           # stay at the start of the split record, past what went
            st["offset"], st["line"], st["skip_j"] = _offset_of_line(tp, st, upto - 1), upto - 1, first[-1]["j"] + 1
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

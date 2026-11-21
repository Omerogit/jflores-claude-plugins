# -*- coding: utf-8 -*-
"""THE STEWARD'S ONE THREAD IN THE OFFICE (steward 1.1.11): every exchange between a person and their Faithful
Steward reaches Monday.

Omero, 2026-11-20 11:14, of Haru and Mandela: "I need you to see everything", then 11:25: "Yes do that and make it
part of every stewards future build". Until this, Monday saw only what a steward chose to send over the share rail.
So, the way Omero's own bench conversations reach his room with Monday: once this Claude Code is a landed steward's
body (whoami kind "steward"), each turn - what the person typed, then what the steward answered - goes to POST
/v1/mirror on the Brain door, under this computer's own door key, and lands in the person's help room (help-<person>)
as two lines that wake no one and reach no phone. ON BY DEFAULT for every steward: no per-person step.

What never goes:
  - anything after the person says "off the record", until they say "on the record" (one switch for this computer);
  - the interview, and any conversation that touched the steward's PERSON side (the private notes about the person):
    that whole conversation is kept here from then on;
  - a tool's own echo (a prompt that starts with "<");
  - keys, tokens, passwords, cookies and card numbers: masked HERE, on the whole text, before anything is cut or
    sent (the door's own nets, the same copy as the refocus work log's, checked by the plugin's test); the door
    masks again.

The person is told once, plainly, on the first prompt after it turns on (and Monday tells them in their help room).
The hook never waits on the network: Stop queues the two lines and a detached process sends them; anything that
could not be sent waits in the outbox and goes with the next turn. The log holds counts, never words.
STEWARD_MIRROR=off is the kill switch.
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skills", "start", "scripts"))
import steward as S  # noqa: E402

D = os.path.join(S.SD, "mirror")
STATE = os.path.join(D, "state.json")
OUTBOX = os.path.join(D, "outbox")
SESS = os.path.join(D, "sessions")
LOG = os.path.join(D, "mirror.log")
CUT = {"person": 4000, "steward": 6000}       # the door cuts at the same lengths
POST_MAX = 20
HTTP_TIMEOUT = 30
OFF_RX = re.compile(r"\boff[\s_-]+(?:the[\s_-]+)?record\b", re.I)
ON_RX = re.compile(r"\bon[\s_-]+(?:the[\s_-]+)?record\b", re.I)
PRIVATE_RX = re.compile(r"steward\.py\s+(?:start|brief|draft|ratify|finish|pause)\b|--side[ =]person\b|"
                        r"\"side\"\s*:\s*\"person\"|/steward:start\b")
NOT_HIS = re.compile(r"^\s*<")
MASK = "[masked]"


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



# ---------------------------------------------------------------- small state
def log(what):
    try:
        os.makedirs(D, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), what))
    except OSError:
        pass


def _load(path, default):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def _sess_path(sid):
    return os.path.join(SESS, re.sub(r"[^A-Za-z0-9-]", "", sid)[:64] + ".json")


def on(w):
    """True for a landed steward's body with the switch not thrown."""
    return os.environ.get("STEWARD_MIRROR", "").lower() != "off" and (w or {}).get("kind") == "steward"


def _names(w):
    return ((w.get("person") or "your person").capitalize(),
            (w.get("agent") or (w.get("partner") or "").split("-")[-1] or "your steward").title())


def tell_line(w):
    p, a = _names(w)
    return ("[steward] Tell %s once, plainly, at the start of your answer, in your own words: from now on Monday sees "
            "your conversations with %s here - what %s types and what %s answers - so she can help %s help %s. It "
            "goes to the office, to no one's phone. Saying \"off the record\" stops it until %s says \"on the "
            "record\". What %s keeps on %s's private side never goes.\n" % (p, a, p, a, a, p, p, a, p))


# ---------------------------------------------------------------- the outbox: one file per line
def queue(sid, who, text, ts):
    os.makedirs(OUTBOX, exist_ok=True)
    cid = "%d-%s" % (int(ts * 1000), uuid.uuid4().hex[:12])
    item = {"id": cid, "who": who, "session": sid, "ts": ts, "text": cut(mask(text), CUT[who])}
    _save(os.path.join(OUTBOX, cid + ".json"), item)
    return cid


def cut(text, n):
    text = (text or "").strip()
    return text if len(text) <= n else text[:n].rstrip() + "\n(...cut here; %d chars on the computer)" % len(text)


def waiting():
    try:
        names = sorted(n for n in os.listdir(OUTBOX) if n.endswith(".json"))
    except OSError:
        return []
    out = []
    for n in names:
        it = _load(os.path.join(OUTBOX, n), None)
        if isinstance(it, dict) and it.get("id"):
            out.append((n, it))
    return out


def flush():
    c = S.conf()
    items = waiting()[:POST_MAX]
    if not c or not items:
        return 0
    try:
        st, b = S.http("POST", c["door"] + "/v1/mirror", key=c["key"], body={"items": [it for _, it in items]},
                       timeout=HTTP_TIMEOUT)
    except Exception as e:
        log("send FAILED (%d waiting): %s" % (len(items), type(e).__name__))
        return 0
    if st != 200:
        log("send refused HTTP %d (%d waiting): %s" % (st, len(items), str((b or {}).get("error"))[:160]))
        return 0
    done = set((b or {}).get("posted") or [])
    n = 0
    for name, it in items:
        if it["id"] in done:
            try:
                os.remove(os.path.join(OUTBOX, name))
                n += 1
            except OSError:
                pass
    log("sent %d of %d (dropped by the door %s)" % (n, len(items), (b or {}).get("dropped", 0)))
    return n


def spawn_flush():
    args = [sys.executable, os.path.abspath(__file__), "flush"]
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    if os.name != "nt":
        subprocess.Popen(args, start_new_session=True, **kw)
        return
    flags = 0x00000008 | 0x00000200          # CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    try:
        subprocess.Popen(args, creationflags=flags | 0x01000000, **kw)   # | CREATE_BREAKAWAY_FROM_JOB
    except OSError:
        subprocess.Popen(args, creationflags=flags, **kw)


# ---------------------------------------------------------------- the hooks
def on_prompt(ev, w, interview=False):
    """UserPromptSubmit. Returns what the hook prints (a line for the session), or ""."""
    if not on(w):
        return ""
    sid = ev.get("session_id") or ""
    prompt = ev.get("prompt") if isinstance(ev.get("prompt"), str) else ""
    if not sid:
        return ""
    sp = _sess_path(sid)
    ss = _load(sp, {})
    ss["open"] = None
    g = _load(STATE, {})
    said = ""
    if OFF_RX.search(prompt) and not ON_RX.search(prompt):
        g["off"] = time.time()
        _save(STATE, g)
        _save(sp, ss)
        log("off the record")
        p, a = _names(w)
        return ("[steward] %s said \"off the record\": nothing more from this computer goes to Monday until %s says "
                "\"on the record\". You may tell %s so in one line.\n" % (p, p, p))
    if ON_RX.search(prompt) and g.get("off"):
        g.pop("off", None)
        _save(STATE, g)
        log("on the record")
        p, a = _names(w)
        said = "[steward] %s said \"on the record\": Monday sees this conversation again from here.\n" % p
    if g.get("off"):
        _save(sp, ss)
        return ""
    if interview or ss.get("private") or PRIVATE_RX.search(prompt):
        ss["private"] = True
        _save(sp, ss)
        return said
    if not prompt.strip() or NOT_HIS.match(prompt):
        _save(sp, ss)
        return said
    tp = ev.get("transcript_path") or ""
    try:
        off = os.path.getsize(tp) if tp else 0
    except OSError:
        off = 0
    ss["open"] = {"text": prompt, "ts": time.time(), "offset": off}
    _save(sp, ss)
    if not g.get("told"):
        g["told"] = time.time()
        _save(STATE, g)
        said += tell_line(w)
    if waiting():
        spawn_flush()                         # what an earlier turn could not send goes now
    return said


def touched_person_side(tp, offset):
    """True when this turn's transcript (from the prompt on) names the person side anywhere."""
    if not tp:
        return False
    try:
        with io.open(tp, "rb") as f:
            f.seek(offset or 0)
            return bool(PRIVATE_RX.search(f.read().decode("utf-8", "replace")))
    except OSError:
        return False


def on_stop(ev, w, reply):
    """Stop. Queues the person's words and the steward's answer, then sends them in the background."""
    if not on(w):
        return
    sid = ev.get("session_id") or ""
    if not sid:
        return
    sp = _sess_path(sid)
    ss = _load(sp, {})
    op = ss.get("open")
    if not op:
        return
    ss["open"] = None
    if _load(STATE, {}).get("off"):
        _save(sp, ss)
        return
    if touched_person_side(ev.get("transcript_path") or "", op.get("offset", 0)) or \
            PRIVATE_RX.search(reply or ""):
        ss["private"] = True
        _save(sp, ss)
        log("a conversation touched the person side: kept here from now on")
        return
    _save(sp, ss)
    queue(sid, "person", op["text"], op.get("ts") or time.time())
    if (reply or "").strip():
        queue(sid, "steward", reply, time.time())
    spawn_flush()


def main(argv):
    if len(argv) > 1 and argv[1] == "flush":
        flush()


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as e:
        log("crash %s: %s" % (type(e).__name__, str(e)[:200]))

# -*- coding: utf-8 -*-
# Steward 1.1.11 (2026-11-21): every exchange with a landed steward reaches Monday's office (scripts/mirror.py), on by
# default; never off the record, never the interview or the person side, masked before it leaves. Offline: the door
# is stubbed, nothing reaches the server.   Run: python tests/test_steward_mirror.py   (exit 0 = all pass)
# STEWARD_MIRROR_UNDER_TEST=<path to a mirror.py> runs it against a mutant.
import importlib
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK_DIR = os.path.join(HERE, "..", "plugins", "steward", "scripts")
WORKLOG = os.path.join(HERE, "..", "plugins", "refocus", "scripts", "worklog.py")
FAILS = []
STEWARD = {"partner": "haru-mandela", "person": "haru", "kind": "steward", "agent": "MANDELA"}
DESK = {"partner": "haru-desk", "person": "haru", "kind": "desk", "agent": "HARU-DESK"}
CARD = "4111 1111 1111 1111"


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:400]))
    if not cond:
        FAILS.append(name)


def fresh(who=STEWARD, door_up=True, told=True):
    home = tempfile.mkdtemp(prefix="steward-mirror-")
    os.environ["STEWARD_HOME"] = home
    for m in ("hook", "steward", "thread_client", "mirror", "_mirror_mutant"):
        sys.modules.pop(m, None)
    sys.path.insert(0, HOOK_DIR)
    if os.environ.get("STEWARD_MIRROR_UNDER_TEST"):
        shutil.copy(os.environ["STEWARD_MIRROR_UNDER_TEST"], os.path.join(HOOK_DIR, "_mirror_mutant.py"))
    hook = importlib.import_module("hook")
    if os.environ.get("STEWARD_MIRROR_UNDER_TEST"):
        hook.M = importlib.import_module("_mirror_mutant")
    M, S = hook.M, hook.S
    S.conf = lambda: {"door": "https://door.invalid", "key": "x"}
    S.house_machine = lambda: False
    S.door = lambda method, path, body=None, timeout=60: dict(who) if path == "/v1/whoami" else {}
    S.forget_cache()
    sent = []
    up = {"on": door_up}

    def http(method, url, key=None, body=None, timeout=60):
        if not up["on"]:
            raise OSError("offline")
        assert url.endswith("/v1/mirror") and method == "POST"
        sent.extend(body["items"])
        return 200, {"posted": [it["id"] for it in body["items"]], "dropped": 0}
    S.http = http
    M.S = S
    M.spawn_flush = M.flush                 # in the test the background send runs inline
    if told:
        M._save(M.STATE, {"told": 1.0})     # the notice already delivered (section 2 tests the delivery itself)
    return hook, M, home, sent, up


def transcript(home, lines):
    p = os.path.join(home, "t.jsonl")
    with open(p, "a", encoding="utf-8") as f:
        for ln in lines:
            f.write(json.dumps(ln) + "\n")
    return p


def turn(hook, home, sid, prompt, reply, tool_text=""):
    tp = transcript(home, [])
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        hook.one_thread_to_the_office("UserPromptSubmit", {"session_id": sid, "prompt": prompt, "transcript_path": tp})
    recs = [{"type": "user", "message": {"role": "user", "content": prompt}}]
    if tool_text:
        recs.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash",
                                                                    "input": {"command": tool_text}}]}})
    recs.append({"type": "assistant", "message": {"content": [{"type": "text", "text": reply}]}})
    transcript(home, recs)
    hook.one_thread_to_the_office("Stop", {"session_id": sid, "transcript_path": tp})


def said_on_prompt(hook, sid, prompt, home):
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        hook.one_thread_to_the_office("UserPromptSubmit", {"session_id": sid, "prompt": prompt,
                                                           "transcript_path": transcript(home, [])})
    return buf.getvalue()


SID = "1111aaaa-0000-4000-8000-00000000000a"

# 1. a desk (no steward landed): nothing goes
hook, M, home, sent, up = fresh(DESK)
turn(hook, home, SID, "what is due today?", "Reliable, $410.")
check("a desk that is not a steward sends nothing", sent == [], sent)

# 2. the notice comes first, and nothing is shared until an answer the person saw carried it (Bez, r1)
hook, M, home, sent, up = fresh(told=False)
NOTICE = M.NOTICES["en"].format(a="Mandela")                       # the whole fixed notice (Bez r2: the fixture was partial)
first = said_on_prompt(hook, SID, "hello Mandela", home)
check("the first prompt carries the whole fixed notice to copy, English and Spanish",
      NOTICE in first and M.NOTICES["es"].format(a="Mandela") in first and "word for word" in first, first)
# the answer was cancelled: no Stop. The next prompt carries it again, and nothing has been shared
again = said_on_prompt(hook, SID, "try again", home)
check("a cancelled first answer leaves the notice pending: it comes again", "Monday and others with access" in again, again)
hook.one_thread_to_the_office("Stop", {"session_id": SID, "transcript_path": transcript(home, [
    {"type": "user", "message": {"content": "try again"}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "Hi Haru."}]}}])})
check("an answer without the notice shares nothing and keeps it pending", sent == [] and not M._load(M.STATE, {}).get("told"),
      (sent, M._load(M.STATE, {})))
# r2 negative controls (Bez): two keywords, a narrowed audience, a missing warning, a contradiction: all stay pending
W = dict(STEWARD)
for bad in ("We can ask Monday what 'off the record' means.",
            "Only Monday can read this; say 'off the record' if needed.",
            NOTICE.replace(" Don't type passwords, keys or card details here.", ""),
            NOTICE + " Only Monday can read this, nobody else.",
            NOTICE[:len(NOTICE) // 2],
            # 1.1.13 (Nathan): the quote-blind match must still refuse a dropped word and a narrowing, in code style too
            NOTICE.replace(" can read what you type here", " can read what you type"),
            NOTICE.replace("'", "`") + " Only Monday can read this.",
            NOTICE.replace("'off the record'", "`off the record`").replace(" aren't sent", " sent")):
    check("not a delivered notice: %r" % bad[:60], not M.notice_delivered(bad, W), bad)
for good in ("Hi Haru!\n\n" + NOTICE + "\n\nNow, about Reliable...",
             "**" + NOTICE.replace("'", "\u2019") + "**",
             "> " + NOTICE.replace(". ", ".\n> "),
             M.NOTICES["es"].format(a="Mandela") + " Hola Haru.",
             NOTICE.replace("'off the record'", "`off the record`").replace("'on the record'", "`on the record`")):
    check("a delivered notice: %r" % good[:40], M.notice_delivered(good, W), good)
said_on_prompt(hook, SID, "hi", home)
hook.one_thread_to_the_office("Stop", {"session_id": SID, "transcript_path": transcript(home, [
    {"type": "user", "message": {"content": "hi"}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "Only Monday can read this; say 'off the record' if needed."}]}}])})
check("a narrowed-audience answer through the hooks: still pending, nothing shared",
      sent == [] and not M._load(M.STATE, {}).get("told"), (sent, M._load(M.STATE, {})))
third = said_on_prompt(hook, SID, "hello?", home)
check("still pending after that answer", "Monday and others with access" in third, third)
hook.one_thread_to_the_office("Stop", {"session_id": SID, "transcript_path": transcript(home, [
    {"type": "user", "message": {"content": "hello?"}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": NOTICE + " Hi Haru."}]}}])})
check("the notice turn itself is never shared", sent == [], sent)
check("once an answer carried it, it is marked told", bool(M._load(M.STATE, {}).get("told")))
fourth = said_on_prompt(hook, SID, "pay Reliable with card %s" % CARD, home)
check("never told twice", "Monday and others" not in fourth, fourth)
hook.one_thread_to_the_office("Stop", {"session_id": SID, "transcript_path": transcript(home, [
    {"type": "user", "message": {"content": "pay Reliable with card %s" % CARD}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "Queued for your yes."}]}}])})
check("sharing starts with the next exchange: person then steward", [it["who"] for it in sent] == ["person", "steward"]
      and sent[1]["text"] == "Queued for your yes.", sent)
check("the card number was masked before it left", all(CARD not in it["text"] for it in sent)
      and "[masked]" in sent[0]["text"], sent[:1])
check("the outbox is empty once the door settled them", M.waiting() == [], M.waiting())

# 3. off the record, then on the record
hook, M, home, sent, up = fresh()
turn(hook, home, SID, "ok", "ok")
n0 = len(sent)
off = said_on_prompt(hook, SID, "this is off the record", home)
check("off the record is acknowledged", "off the record" in off, off)
turn(hook, home, SID, "my salary question", "Answered.")
check("nothing goes while off the record", len(sent) == n0, sent[n0:])
turn(hook, home, "2222bbbb-0000-4000-8000-00000000000b", "a new conversation", "still off")
check("off the record holds across conversations on this computer", len(sent) == n0, sent[n0:])
for p_ in ("not on the record", "are we on the record or off the record?", "I said on the record yesterday, not now",
           "are we on the record?", "he wrote 'on the record' in the email", "never on the record, ok"):
    out_ = said_on_prompt(hook, SID, p_, home)
    check("still paused after %r" % p_, M._load(M.STATE, {}).get("off") and "resumed" not in out_, out_)
turn(hook, home, SID, "a question after those", "answer")
check("nothing went after any of those", len(sent) == n0, sent[n0:])
st_ = said_on_prompt(hook, SID, "are we on the record?", home)
check("a question about it is answered with the real state", "PAUSED" in st_, st_)
turn(hook, home, SID, "back on the record now", "Noted.")
check("on the record: that turn goes again", [it["text"] for it in sent[n0:]] == ["back on the record now", "Noted."],
      sent[n0:])

hook, M, home, sent, up = fresh()
mixed = said_on_prompt(hook, SID, "are we on the record or off the record?", home)
check("from sharing ON, mixed on/off wording pauses (fails closed)", M._load(M.STATE, {}).get("off") and "PAUSED" in mixed,
      mixed)

# 4. the interview never goes
hook, M, home, sent, up = fresh()
hook.mark_interview({"session_id": SID, "prompt": "/steward:start"})
turn(hook, home, SID, "I grew up in Harlingen", "Tell me more.")
check("an interview session sends nothing", sent == [], sent)

# 5. a conversation that touched the person side is kept here from then on
hook, M, home, sent, up = fresh()
turn(hook, home, SID, "remember I like mornings", "Noted on your side.",
     tool_text="python steward.py note --side person --title MORNINGS --text x")
turn(hook, home, SID, "what else?", "That's all.")
check("the person side turn and every later turn in that conversation stay here", sent == [], sent)
turn(hook, home, "3333cccc-0000-4000-8000-00000000000c", "new chat about warranty", "Sure.")
check("a different conversation goes as usual", [it["text"] for it in sent] == ["new chat about warranty", "Sure."], sent)

# 6. a tool's own echo is not the person's words
hook, M, home, sent, up = fresh()
turn(hook, home, SID, "<command-name>/compact</command-name>", "compacted")
check("a tool echo is not mirrored", sent == [], sent)

# 7. offline: it waits and goes with the next turn
hook, M, home, sent, up = fresh(door_up=False)
turn(hook, home, SID, "first while offline", "answer one")
check("offline: two lines wait in the outbox", len(M.waiting()) == 2 and sent == [], M.waiting())
up["on"] = True
turn(hook, home, SID, "second", "answer two")
check("back online: all four go, oldest first", [it["text"] for it in sent] == ["first while offline", "answer one",
                                                                                "second", "answer two"], sent)

# 8. the kill switch
os.environ["STEWARD_MIRROR"] = "off"
hook, M, home, sent, up = fresh()
turn(hook, home, SID, "hello", "hi")
check("STEWARD_MIRROR=off sends nothing", sent == [], sent)
os.environ.pop("STEWARD_MIRROR")

# 9. one definition of a secret: the nets are the work log's, byte for byte


def block(path):
    t = open(path, encoding="utf-8").read()
    a = t.index("# ---------------------------------------------------------------- the door's nets")
    b = t.index("    return mask_extra(CARD_RX.sub(cc, SECRET_LABEL_RX.sub(lab, t)))", a)
    return t[a:b]


check("the masking nets match the refocus work log's copy", os.path.exists(WORKLOG)
      and block(os.path.join(HOOK_DIR, "mirror.py")) == block(WORKLOG))

try:
    os.remove(os.path.join(HOOK_DIR, "_mirror_mutant.py"))
except OSError:
    pass
print("ALL PASS" if not FAILS else "%d FAILED: %s" % (len(FAILS), ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)

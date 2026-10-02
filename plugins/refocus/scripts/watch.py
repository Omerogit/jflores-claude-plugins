# -*- coding: utf-8 -*-
# UserPromptSubmit - when the window is filling, tell the session to ASK the person, once, about a refocus cut.
#
# Omero, 2026-09-23: "Maybe it should be a nudge and not automatic. That way, they can choose, and ask them, 'Do
# you want to compact?' If they say yes, then run it automatically." And on how it is said: "we don't want to be
# repeating the same thing over and over and make it look like it's just some program running." So this hands
# the session the four things the question must carry and two sample phrasings drawn at random - never a script.
#
# The size is measured, not guessed: every assistant record in the transcript carries its own usage, and
# input + cache_read + cache_creation is the context that turn paid for. It fires once at 40% of the model's
# window and re-arms when the window drops back under the line (after a compaction).
#
# It also carries the share rail's answers (1.4.0, 2026-10-02): when something was shared from this computer, it
# looks for the house's answer at most once a minute and hands it to the session to show the person (share_answers).
import io
import json
import os
import random
import sys

HOME = os.path.expanduser("~")
D = os.environ.get("REFOCUS_HOME") or os.path.join(HOME, ".claude", "refocus")   # REFOCUS_HOME: tests only
QUIET = os.path.join(D, "quiet.json")
CONF = os.path.join(D, "door.json")
FRACTION = 0.40
TAIL_BYTES = 600000
TEST_LINE = int(os.environ.get("REFOCUS_WATCH_TEST_LINE") or 0)   # tests only: fire above this many tokens

ASKS = [
    "This conversation is getting long - I'm about {p}% full. Want me to save my notes and run the refocus "
    "protocol, then compact it? Nothing on your screen gets deleted. If you'd rather I never ask, say 'stop asking'.",
    "Quick one: I'm at about {p}% of what I can hold. I can save my notes, run the refocus protocol and compact - "
    "everything here stays put. Want me to? (Say 'stop asking' if you'd rather I didn't bring this up.)",
    "Heads up - I'm around {p}% full. If you're good with it, I'll save my notes, refocus and compact so I stay "
    "sharp. Nothing on your screen goes away. Not interested? Say 'stop asking' and I won't raise it again.",
    "We've covered a lot - I'm near {p}% full. Should I save my notes, do a refocus and compact? You keep "
    "everything you see here. And if these check-ins bug you, 'stop asking' turns them off.",
    "Before we keep going: I'm about {p}% full. I'd like to save my notes, run the refocus protocol and compact - "
    "nothing you see here goes away. OK with you? You can also say 'stop asking' any time.",
    "I'm getting full, about {p}%. Want me to save where we are, refocus and compact? The conversation stays on "
    "screen. If you'd prefer I never ask, just say 'stop asking'.",
]


def window(model):
    """Measured windows in Claude Code; anything unknown gets the smallest, because warning early costs a sentence."""
    m = (model or "").lower()
    if m.startswith("claude-opus-5") or "[1m]" in m:
        return 1000000
    if m.startswith("claude-fable"):
        return 280000
    return 200000


def last_usage(tp):
    size = os.path.getsize(tp)
    with io.open(tp, "rb") as f:
        f.seek(max(0, size - TAIL_BYTES))
        lines = f.read().decode("utf-8", "replace").split("\n")
    if size > TAIL_BYTES:
        lines = lines[1:]
    for line in reversed(lines):
        if "compact_boundary" in line:
            try:
                if json.loads(line).get("subtype") == "compact_boundary":
                    return None, None       # a cut happened after the newest usage: unknown beats wrong
            except Exception:
                pass
        if '"usage"' not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("isSidechain"):
            continue
        msg = rec.get("message") or {}
        model = msg.get("model") or ""
        if model.startswith("<"):           # Claude Code's "<synthetic>" placeholder is not a model
            continue
        u = msg.get("usage") or {}
        tot = ((u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
               + (u.get("cache_creation_input_tokens") or 0))
        if tot > 1000:
            return tot, model
    return None, None


SHARE = os.path.join(D, "share.json")
SHARE_OPEN_DAYS = 14                   # look for answers this long after the last share
SHARE_EVERY = int(os.environ.get("REFOCUS_SHARE_EVERY") or 60)      # seconds between looks (tests: 0)


def share_answers():
    """The share rail (2026-10-02): if something was shared lately, look - at most once a minute, four seconds at
    most - for answers from the house, and hand them to the session to show the person. Silent on any failure:
    the person's message must never wait on the door."""
    import time
    import urllib.request
    try:
        with open(SHARE, encoding="utf-8") as f:
            st = json.load(f)
        with open(CONF, encoding="utf-8-sig") as f:
            c = json.load(f)
    except Exception:
        return ""
    now = time.time()
    if now - st.get("last_share", 0) > SHARE_OPEN_DAYS * 86400 or now - st.get("checked", 0) < SHARE_EVERY:
        return ""
    # Two copies of this hook can run at once (the plugin installed twice): only the one that claims the look speaks.
    lock = SHARE + ".look"
    try:
        if os.path.exists(lock) and now - os.path.getmtime(lock) < max(SHARE_EVERY, 2):
            return ""
        fd = os.open(lock + ".%d" % os.getpid(), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        os.close(fd)
        os.replace(lock + ".%d" % os.getpid(), lock)
    except Exception:
        return ""
    st["checked"] = now
    try:
        req = urllib.request.Request(c["door"] + "/v1/share/replies?since=%r" % float(st.get("seen", 0)), headers={
            "Accept": "application/json", "User-Agent": "refocus-plugin/watch-1.4", "Authorization": "Bearer " + c["key"]})
        with urllib.request.urlopen(req, timeout=4) as r:
            msgs = json.loads(r.read().decode("utf-8") or "{}").get("messages") or []
    except Exception:
        msgs = []
    if msgs:
        st["seen"] = max(st.get("seen", 0), max(m["ts"] for m in msgs))
    try:
        with open(SHARE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(st, f)
        os.replace(SHARE + ".tmp", SHARE)
    except Exception:
        return ""
    if not msgs:
        return ""
    parts = ["SHARE RAIL: an answer came back from the J Flores house to what this computer shared (the share skill).\n"
             "It is written to the person. Show it to them first, in full and in plain words, before anything else;\n"
             "then help them do what it says.\n"]
    for m in msgs:
        parts.append("--- from %s ---\n%s\n--- end ---\n" % (m.get("from") or "the house", (m.get("body") or "").rstrip()))
    return "".join(parts)


def main():
    if os.environ.get("OFFICE_SEAT"):
        return                              # an office seat has its own watch
    if not os.environ.get("REFOCUS_IGNORE_HOUSE_WATCH") and (
            os.path.exists(os.path.join(HOME, ".claude", "hooks", "context_watch.py"))   # Omero's bench
            or os.path.exists(os.path.join(HOME, ".claude", "brain.json"))              # a house bench
            or os.path.isdir("/home/monday/office")):                                   # monday-server
        return                              # a house machine has the house watch; never fire twice
    try:
        ev = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return
    answer = share_answers()
    if answer:
        sys.stdout.write(answer)
    if os.path.exists(QUIET):
        return
    tp = ev.get("transcript_path") or ""
    if not tp or not os.path.exists(tp):
        return
    used, model = last_usage(tp)
    if not used:
        return
    win = window(model)
    line = TEST_LINE or int(win * FRACTION)
    stamp = os.path.join(D, "nudged", "%s.stamp" % (ev.get("session_id") or "unknown"))
    if used < line:
        if os.path.exists(stamp):
            try:
                os.remove(stamp)            # re-arm: the window was cut since we last spoke
            except Exception:
                pass
        return
    # Claim the stamp atomically. If the plugin is installed twice (the org's marketplace AND GitHub), two copies
    # of this hook run at once; only the one that creates the stamp speaks, so the person is asked once.
    try:
        os.makedirs(os.path.dirname(stamp), exist_ok=True)
        fd = os.open(stamp, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        return
    except Exception:
        return
    with os.fdopen(fd, "w") as f:
        f.write(str(used))
    pct = int(100.0 * used / win)
    head = ("REFOCUS WATCH: this conversation is about %d%% full (%dk of about %dk on %s). When it fills, it is "
            "replaced by a summary of itself.\n" % (pct, used // 1000, win // 1000, model or "this model"))
    if not os.path.exists(CONF):
        sys.stdout.write(head +
            "This machine has NO BRAIN CONNECTED, so the refocus protocol cannot save notes first. Finish what was\n"
            "asked. Then tell the person ONCE, in your own words: the conversation is getting full; to save notes\n"
            "before compacting they need their brain link from Omero (paste it and say 'connect my brain'); they\n"
            "can still type /compact themselves any time; 'stop asking' turns these notes off. Do not file or cut.\n"
            "This fires once and re-arms after the next compaction.\n")
        return
    a, b = random.sample(ASKS, 2)
    sys.stdout.write(head +
        "Finish what was asked first. Then ask the person ONCE, in your own words - never a script (Omero: \"we\n"
        "don't want to be repeating the same thing over and over and make it look like it's just some program\n"
        "running\"). It must carry four things:\n"
        "  1. how full you are (about %d%%)   2. the offer: save your notes, run the refocus protocol, then compact\n"
        "  3. nothing on their screen goes away   4. 'stop asking' turns these off.\n"
        "Plain words (no 'CONTINUITY', no 'cut'). Two ways it could sound - do NOT copy either:\n"
        "  - %s\n  - %s\n"
        "Never compact on your own. A yes: run the refocus-cut skill straight through; it ends with the person\n"
        "typing /compact. NEVER /clear - a clear wipes their conversation off the screen. A no, or no answer:\n"
        "drop it. 'Stop asking': the skill's `quiet` command. This fires once and re-arms after the next compaction.\n"
        % (pct, a.format(p=pct), b.format(p=pct)))


try:
    main()
except Exception:
    pass
sys.exit(0)

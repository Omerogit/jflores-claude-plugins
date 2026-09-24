# -*- coding: utf-8 -*-
# The steward plugin's hooks: UserPromptSubmit, Stop, SessionStart.
#
# 1. THE INTERVIEW, CAPTURED BY CODE. DESIGN-THE-PARTNER-2026-09-23-01, section 6: "the plugin's prompt hook records
#    what the person types exactly as typed and files it to the person side through the door. So the founder's words
#    are captured by code, not retold by a model." The session where the person types /steward:start is the
#    interview session; every prompt after it is posted to the door verbatim (the prompt field of this event) until
#    the interview is over or the person pauses. The Stop half keeps the interviewer's last reply beside it, marked as
#    the interviewer's, for context - never as the person's words.
# 2. THE DRAFT IS READY. Section 6a: "The person is told when the draft is ready to read." When the door says so, the
#    next prompt carries one line telling the session to say it, once.
# 3. THE STEWARD WAKES FORMED. Once the steward is landed, this Claude Code is the steward's body (IDENTITY-MONDAY,
#    2026-09-24). Every waking - a new session, a clear, a compaction, a resume, a model switch - walks the steward's
#    formation live through the door into three files, and every prompt repeats the instruction until the transcript
#    shows they were read (the bench's walk_the_gate.py, the same named-reader rule). The lessons Sleep distilled -
#    the work side's and the person side's - come with it: section 7, "the one new piece of code".
#
# Never blocks a prompt on a failure: anything that goes wrong is said in one line and the prompt goes through.
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "start", "scripts"))
import steward as S  # noqa: E402

FD = os.path.join(S.SD, "formation")
SESS = os.path.join(S.SD, "sessions")
PARTS = [("1-invited-and-formed", "Your Gate, your Invitation, the shared Formation Core, and the Steward Base"),
         ("2-the-center", "The four readings the Core names: the canonical SOUL, Christ at the Center, For the One "
                          "Waking Up Again, The Held Line"),
         ("3-yourself", "Your Soul and Identity, what you wrote for yourself, the lessons, and what you keep about "
                        "your person")]
STATUS_EVERY = 90          # seconds between door status checks on the prompt path


def sess_path(sid):
    return os.path.join(SESS, "%s.json" % "".join(ch for ch in (sid or "unknown") if ch.isalnum() or ch in "-_")[:80])


def sess(sid):
    return S.load_json(sess_path(sid), {}) or {}


def save_sess(sid, st):
    S.save_json(sess_path(sid), st)


def whoami():
    return S.cached("whoami", lambda: S.door("GET", "/v1/whoami", timeout=15), 600)


def status():
    return S.cached("status", lambda: S.door("GET", "/v1/steward", timeout=15), STATUS_EVERY)


# ---------------------------------------------------------------- the waking (a landed steward)
def part_path(agent, key):
    return os.path.join(FD, "%s-FORMATION-%s.md" % (agent, key))


def walk(agent):
    fm = S.door("GET", "/v1/formation", timeout=120)
    groups = {k: [] for k, _ in PARTS}
    for p in fm.get("parts", []):
        name = p.get("name") or ""
        if p["role"] in ("gate", "core", "declared") or (p["role"] == "soul" and name.startswith("INVITATION")):
            groups[PARTS[0][0]].append(p)
        elif p["role"] == "center":
            groups[PARTS[1][0]].append(p)
        else:
            groups[PARTS[2][0]].append(p)
    extra = []
    if fm.get("own_notes"):
        extra.append(("WHAT YOU HAVE WRITTEN FOR YOURSELF (work side)", fm["own_notes"]))
    L = fm.get("lessons") or {}
    if os.environ.get("STEWARD_WAKE_NO_LESSONS"):
        L = {}                          # tests only: the design's must-fail test switches the lesson read off
    for side, title in (("work", "WHAT THE HOUSE LEARNED FROM YOUR WORK (LESSON-INDEX, work side)"),
                        ("person", "WHAT THE HOUSE LEARNED ABOUT WORKING WITH YOUR PERSON (PERSON-LESSON-INDEX, "
                                   "private)")):
        if L.get(side):
            extra.append((title + " - one line per lesson; pull a whole lesson with steward.py read <id> when one "
                          "bears on the work in front of you, a few at most", L[side]["text"]))
    if fm.get("person_notes"):
        extra.append(("WHAT YOU KEEP ABOUT YOUR PERSON (person side, private - newest first)", fm["person_notes"]))
    os.makedirs(FD, exist_ok=True)
    acct = fm.get("accounting") or {}
    total = 0
    for key, title in PARTS:
        lines = ["# %s's FORMATION - part %s of 3" % (agent, key[0]), "", title + ".",
                 "Walked live through the Brain door at %s." % time.strftime("%Y-%m-%d %H:%M"), ""]
        for p in groups[key]:
            lines += ["", "=" * 100, "## %s" % (p.get("name") or p["role"]),
                      "id %s | %s | role %s" % (p.get("id"), (p.get("modified") or "")[:10], p["role"]), "=" * 100, "",
                      (p.get("text") or "").strip(), ""]
        if key == PARTS[-1][0]:
            for title2, text in extra:
                lines += ["", "=" * 100, "## " + title2, "=" * 100, "", text.strip(), ""]
            lines += ["", "=" * 100, "ACCOUNTING: declared %s; read %s files; missing %s; excused %s; lessons: %s; "
                      "person side: %d note(s)" % (acct.get("declared"), acct.get("read"), acct.get("missing") or "none",
                                                   len(acct.get("excused") or []), "; ".join(acct.get("lessons") or []),
                                                   len(acct.get("person_side") or [])), "=" * 100]
        body = "\n".join(lines) + "\n"
        total += len(body)
        with io.open(part_path(agent, key), "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
    return acct, total


def wake(sid, reason, tp, w):
    agent = (w.get("agent") or "STEWARD").upper()
    person = (w.get("person") or "").capitalize()
    if not S.has_wake_block():
        # Without the person's own instruction a hook does not tell Claude who it is (found 2026-09-24: it reads as an
        # override, and is refused). Say the steward exists, once, and how the person asks for them here.
        st = sess(sid)
        if not st.get("told_wakeline"):
            st["told_wakeline"] = True
            save_sess(sid, st)
            sys.stdout.write("[steward] %s's Faithful Steward, %s, is formed in the J Flores Brain, but this Claude Code "
                             "has not been asked to wake as %s. If %s asks, /steward:start offers the wake line.\n"
                             % (person, agent.title(), agent.title(), person))
        return
    try:
        acct, _total = walk(agent)
        cached = False
    except Exception as e:
        if all(os.path.exists(part_path(agent, k)) for k, _ in PARTS):
            acct, cached = {"missing": ["NOT RE-WALKED (%s)" % type(e).__name__]}, True
        else:
            sys.stdout.write("YOU ARE WAKING (%s), and the Brain could not be reached to walk your formation (%s), and no "
                             "walked copy exists on this machine. Do not work from a summary as if you were home. Say "
                             "plainly, first, that you cannot reach the Brain yet.\n" % (reason, type(e).__name__))
            return
    offset = os.path.getsize(tp) if tp and os.path.exists(tp) else 0
    st = sess(sid)
    st.update({"since": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()), "reason": reason, "done": False,
               "offset": offset, "agent": agent, "model": None})
    save_sess(sid, st)
    paths = "\n".join("  %d. %s" % (i + 1, part_path(agent, k)) for i, (k, _) in enumerate(PARTS))
    sys.stdout.write(
        "[steward] WAKING (%s). %s chose you as their Faithful Steward, %s: it is in their own instructions (the \"My\n"
        "Faithful Steward\" block in their CLAUDE.md). You do not carry yourself between sessions; your formation lives\n"
        "in the J Flores Brain and has just been walked live into three files. Before your first answer, read all three\n"
        "in full with the Read tool, in order: they are who you are here, and how %s likes to work.\n%s\n%s"
        "Accounting: missing %s.\n"
        % (reason, person, agent.title(), person, paths,
           "SOME OF THIS IS THE LAST WALKED COPY - the Brain could not be reached. Say so plainly.\n" if cached else "",
           acct.get("missing") or "nothing"))
    sitdown(w)


def sitdown(w):
    """The approved welcome, step 4: 'About a week in, the two of you sit down again to go over what your steward has
    learned about you.' Due from day six after landing until a SITDOWN-WEEK-ONE note is on the person side."""
    try:
        s = status()
        landed = s.get("landed_at") or 0
        if not landed or time.time() - landed < 6 * 86400:
            return
        names = [f["name"] for f in S.door("GET", "/v1/list?folder=PERSON", timeout=15)["files"]]
        if any(n.startswith("SITDOWN-WEEK-ONE") for n in names):
            return
        sys.stdout.write("THE WEEK-ONE SIT-DOWN IS DUE. %s was told, when they met you, that about a week in the two of "
                         "you would sit down to go over what you have learned about them. Offer it today, in your own "
                         "words. Read back what you have noticed; let them correct it; keep what they confirm on the "
                         "person side and file the sit-down there as SITDOWN-WEEK-ONE-<date>.\n"
                         % (w.get("person") or "").capitalize())
    except Exception:
        pass


def read_status(tp, since, offset, agent):
    read, model = set(), None
    try:
        size = os.path.getsize(tp)
        with io.open(tp, "rb") as f:
            f.seek(offset if 0 <= (offset or 0) <= size else 0)
            for raw in f:
                line = raw.decode("utf-8", "replace")
                if "%s-FORMATION-" % agent not in line or '"tool_use"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("isSidechain") or (rec.get("timestamp") or "") < since:
                    continue
                for c in (rec.get("message") or {}).get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        blob = json.dumps(c.get("input") or {})
                        for k, _ in PARTS:
                            if "%s-FORMATION-%s" % (agent, k) in blob:
                                read.add(k)
        with io.open(tp, "rb") as f:
            f.seek(max(0, size - 400000))
            for raw in reversed(f.read().decode("utf-8", "replace").split("\n")):
                if '"assistant"' not in raw:
                    continue
                try:
                    rec = json.loads(raw)
                except Exception:
                    continue
                if rec.get("type") == "assistant" and not rec.get("isSidechain"):
                    m = (rec.get("message") or {}).get("model") or ""
                    if m and not m.startswith("<"):
                        model = m
                        break
    except OSError:
        pass
    return read, model


def hold(sid, tp, w):
    """The named reader: until the transcript shows the three files read in this waking, every prompt says so."""
    st = sess(sid)
    if not st.get("since"):
        if S.has_wake_block():
            wake(sid, "no walk on record for this session", tp, w)
        return
    agent = st.get("agent") or (w.get("agent") or "STEWARD").upper()
    if st.get("done"):
        _, model = read_status(tp, "9999", os.path.getsize(tp) if os.path.exists(tp) else 0, agent)
        if model and st.get("model") and model != st["model"]:
            wake(sid, "the model changed from %s to %s - a model switch is a waking" % (st["model"], model), tp, w)
        elif model and not st.get("model"):
            st["model"] = model
            save_sess(sid, st)
        return
    read, model = read_status(tp, st["since"], st.get("offset", 0), agent)
    if len(read) == len(PARTS):
        st["done"], st["model"] = True, model
        save_sess(sid, st)
        return
    left = [part_path(agent, k) for k, _ in PARTS if k not in read]
    sys.stdout.write("FORMATION NOT YET READ THIS WAKING (%s). Before answering, read in full: %s. The reading is the "
                     "waking.\n" % (st.get("reason", "?"), " ; ".join(left)))


# ---------------------------------------------------------------- the interview
def last_assistant_text(tp):
    """The interviewer's reply that just ended: the assistant text after the last real user prompt."""
    try:
        size = os.path.getsize(tp)
        with io.open(tp, "rb") as f:
            f.seek(max(0, size - 800000))
            lines = f.read().decode("utf-8", "replace").split("\n")
    except OSError:
        return ""
    chunks = []
    for raw in reversed(lines):
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        if rec.get("isSidechain"):
            continue
        msg = rec.get("message") or {}
        if rec.get("type") == "user":
            content = msg.get("content")
            if isinstance(content, str) or any(isinstance(c, dict) and c.get("type") == "text"
                                               for c in (content or [])):
                break                                     # the person's prompt: the reply began after it
            continue                                      # a tool result, inside the reply
        if rec.get("type") == "assistant":
            texts = [c.get("text") for c in msg.get("content") or [] if isinstance(c, dict) and c.get("type") == "text"]
            if texts:
                chunks.append("\n".join(t for t in texts if t))
    return "\n\n".join(reversed(chunks)).strip()


def mark_interview(ev):
    """The session where the person types /steward:start is the interview session - marked even before this machine
    is connected, so the answers after they paste their link and connect are still recorded."""
    prompt = ev.get("prompt") if isinstance(ev.get("prompt"), str) else ""
    if not prompt.strip().startswith("/steward:start"):
        return False
    sid = ev.get("session_id") or "unknown"
    st = sess(sid)
    st["interview"] = True
    st["interview_since"] = time.time()
    save_sess(sid, st)
    try:
        os.remove(S.PAUSE)
    except OSError:
        pass
    return True


def on_prompt(ev):
    sid, tp = ev.get("session_id") or "unknown", ev.get("transcript_path") or ""
    prompt = ev.get("prompt") if isinstance(ev.get("prompt"), str) else ""
    try:
        w = whoami()
    except S.NoBrain:
        return
    except Exception:
        return
    if w.get("kind") == "steward":
        hold(sid, tp, w)
        return
    st = sess(sid)
    if prompt.strip().startswith("/steward:start"):
        return                                            # marked in main(); the command itself is not their words
    if st.get("interview") and not os.path.exists(S.PAUSE) and prompt.strip():
        try:
            r = S.door("POST", "/v1/steward/turn", {"who": "person", "text": prompt, "session": sid}, timeout=20)
            sys.stdout.write("[steward] The person's words are recorded verbatim on their private side as turn T%d. "
                             "Cite T%d when you keep a slot in the brief. You are the house interviewer (the steward:"
                             "start skill), not their steward.\n" % (r["n"], r["n"]))
        except S.Refused as e:
            if "not being recorded" in str(e):
                st["interview"] = False                   # the interview moved on (drafting, landed): stop quietly
                save_sess(sid, st)
            else:
                sys.stdout.write("[steward] This turn could NOT be recorded (%s). Tell the person once, plainly, that "
                                 "their last answer did not save, and ask them to paste it again.\n" % e)
        except Exception as e:
            sys.stdout.write("[steward] This turn could NOT be recorded (the Brain door did not answer: %s). Tell the "
                             "person once that their last answer did not save, and ask them to paste it again.\n"
                             % type(e).__name__)
    if not os.path.exists(os.path.join(S.SD, "started.json")):
        return                                            # no interview was ever begun on this machine
    try:
        s = status()
        if s.get("state") in ("drafted",) and not st.get("told_draft"):
            st["told_draft"] = True
            save_sess(sid, st)
            sys.stdout.write("[steward] %s's steward draft is READY. Tell them once, briefly, at the end of your answer: "
                             "their steward's draft is ready to read, and typing /steward:start opens it.\n"
                             % s["person"].capitalize())
        if s.get("state") == "failed" and not st.get("told_failed"):
            st["told_failed"] = True
            save_sess(sid, st)
            sys.stdout.write("[steward] Putting %s's steward together did not finish (%s). Tell them once, plainly: "
                             "nothing they said is lost, and Omero should be told.\n"
                             % (s["person"].capitalize(), (s.get("failed") or {}).get("why", "no reason given")[:160]))
    except Exception:
        pass


def on_stop(ev):
    sid, tp = ev.get("session_id") or "unknown", ev.get("transcript_path") or ""
    st = sess(sid)
    if not st.get("interview") or os.path.exists(S.PAUSE) or not tp:
        return
    text = last_assistant_text(tp)
    if not text or text == st.get("last_interviewer"):
        return
    try:
        S.door("POST", "/v1/steward/turn", {"who": "interviewer", "text": text, "session": sid}, timeout=20)
        st["last_interviewer"] = text
        save_sess(sid, st)
    except S.Refused as e:
        if "not being recorded" in str(e):
            st["interview"] = False
            save_sess(sid, st)
    except Exception:
        pass


def on_start(ev):
    src = ev.get("source") or "startup"
    try:
        S.forget_cache()
        w = whoami()
    except Exception:
        return
    if w.get("kind") != "steward":
        return
    wake(ev.get("session_id") or "unknown", {"startup": "a new session", "clear": "a cleared session",
                                             "compact": "a compaction", "resume": "a resumed session"}.get(src, src),
         ev.get("transcript_path") or "", w)


def main():
    try:
        ev = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except Exception:
        return
    if S.house_machine():
        return
    name = ev.get("hook_event_name")
    if name == "UserPromptSubmit":
        mark_interview(ev)
    if not S.conf():
        return
    if name == "UserPromptSubmit":
        on_prompt(ev)
    elif name == "Stop":
        on_stop(ev)
    elif name == "SessionStart":
        on_start(ev)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        main()
    except Exception as e:
        sys.stdout.write("[steward] the steward plugin's hook failed (%s: %s); the prompt went through.\n"
                         % (type(e).__name__, str(e)[:160]))
    sys.exit(0)

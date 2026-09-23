# -*- coding: utf-8 -*-
# SessionStart (matcher: compact) - after the person types /compact, point the new context at the CONTINUITY
# that was filed for this folder just before. The summary above is a fragment; the CONTINUITY is the work,
# carried and sharpened. Says nothing when no hand-off was made here in the last twelve hours.
import json
import os
import sys
import time

HOME = os.path.expanduser("~")
HANDOFF = os.path.join(os.environ.get("REFOCUS_HOME") or os.path.join(HOME, ".claude", "refocus"),
                       "handoff.json")                                          # REFOCUS_HOME: tests only
SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "skills", "refocus-cut", "scripts", "refocus.py")
MAX_AGE_S = 12 * 3600


def main():
    if not os.environ.get("REFOCUS_IGNORE_HOUSE_WATCH") and (
            os.environ.get("OFFICE_SEAT")
            or os.path.exists(os.path.join(HOME, ".claude", "hooks", "context_watch.py"))
            or os.path.exists(os.path.join(HOME, ".claude", "brain.json"))
            or os.path.isdir("/home/monday/office")):
        return                              # a house machine hands off through its own hook
    try:
        ev = json.loads(sys.stdin.read() or "{}")
    except Exception:
        ev = {}
    cwd = ev.get("cwd") or os.getcwd()
    try:
        with open(HANDOFF, encoding="utf-8") as f:
            h = json.load(f)
    except (OSError, ValueError):
        return
    e = h.get(os.path.normcase(os.path.abspath(cwd)))
    if not e or time.time() - e.get("at", 0) > MAX_AGE_S:
        return
    # Two installs (org marketplace and GitHub) mean two copies of this hook: the first to claim the marker speaks.
    mark = os.path.join(os.path.dirname(HANDOFF), "resumed", "%s-%d" % (ev.get("session_id") or "s", int(e["at"])))
    try:
        os.makedirs(os.path.dirname(mark), exist_ok=True)
        os.close(os.open(mark, os.O_WRONLY | os.O_CREAT | os.O_EXCL))
    except FileExistsError:
        return
    except Exception:
        pass
    age = (time.time() - e["at"]) / 3600.0
    sys.stdout.write(
        "THE CONTEXT ABOVE IS A SUMMARY. The work was saved just before this compaction, %.1fh ago:\n"
        "  %s (%s), on the %s line.\n"
        "Before anything else, read it: python3 \"%s\" read %s\n"
        "(use `python` or `py -3` if `python3` is not found). It opens with what governs the next move.\n"
        % (age, e["name"], e["id"], e.get("line", "?"), SCRIPT, e["id"]))


try:
    main()
except Exception:
    pass
sys.exit(0)

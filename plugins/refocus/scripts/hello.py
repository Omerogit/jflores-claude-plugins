# -*- coding: utf-8 -*-
# SessionStart - tell a new session, once, how this computer reaches the J Flores Brain.
#
# Found 2026-10-02 on Omar's computer: the setup had connected him, yet his Claude Code searched Google Drive for the
# Brain, asked for Drive folders to be shared and for a server key, and reported "Brain config on this machine: None".
# The house skills cite Brain files by Drive id, so a session goes looking there. This names the real route before it
# looks. No network: it reads the stored connection only (the key itself is never printed).
import json
import os
import sys

HOME = os.path.expanduser("~")
D = os.environ.get("REFOCUS_HOME") or os.path.join(HOME, ".claude", "refocus")   # REFOCUS_HOME: tests only
CONF = os.path.join(D, "door.json")


def house_machine():
    if os.environ.get("REFOCUS_IGNORE_HOUSE_WATCH"):
        return False                                   # tests only
    return bool(os.environ.get("OFFICE_SEAT")
                or os.path.exists(os.path.join(HOME, ".claude", "hooks", "context_watch.py"))
                or os.path.exists(os.path.join(HOME, ".claude", "brain.json"))
                or os.path.isdir("/home/monday/office"))


def main():
    if house_machine():
        return
    try:
        with open(CONF, encoding="utf-8-sig") as f:
            c = json.load(f)
    except Exception:
        return                                         # not connected: the refocus watch says so when it matters
    if not (c.get("door") and c.get("key")):
        return
    who = c.get("partner") or "this person's desk"
    sys.stdout.write(
        "J FLORES BRAIN: this computer IS connected, as %s, through the J Flores Brain door (%s). It is not reached\n"
        "through Google Drive. Do not search Drive for it, and do not ask anyone to share Drive folders or give a\n"
        "server key. This computer reaches the person's own desk in the Brain, which is all it is meant to reach.\n"
        "To check or use it: the refocus-cut skill's `refocus.py whoami` (and `read <id>` for the person's own files).\n"
        "Brain ids cited inside house skills (like win-them-over) will not open from here. That is expected: work\n"
        "from the skill text. Anything that needs more (a server, a bot, a credential, a Brain folder) goes to Omero\n"
        "through the share skill (`share.py ask`), never around it.\n" % (who, c["door"]))


try:
    main()
except Exception:
    pass
sys.exit(0)

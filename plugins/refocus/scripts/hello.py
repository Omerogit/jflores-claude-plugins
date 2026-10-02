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
        "through the share skill (`share.py ask`), never around it.\n"
        "HOUSECALL PRO IS CONNECTED TOO, through the same door: customers, jobs and job numbers, line items and part\n"
        "numbers, the schedule, estimates, invoices, memberships, the audit line. Read it with the housecall-pro\n"
        "skill (`hcp.py`), read only. Never say this computer is not connected to Housecall Pro, and never ask for an\n"
        "HCP login or key: the server reads it with the house's own session.\n" % (who, c["door"]))
    welcome(who)


# THE WELCOME (Omero, 2026-10-02: "when anybody installs this, it should somehow ... post it directly under Claude as
# to the benefits and everything that comes along with it (and their ability to send an agent...). This is a great
# process for getting newbies on the server." DECISION-PERSON-AGENT-ROUTE-2026-10-02-01). Once per desk per computer,
# in the first new session after it connects. The facts are fixed; the words are Claude's own (fixed lines "eventually
# sound robotic"). The stamp is claimed atomically, so a plugin installed twice still welcomes once.
WELCOME = """J FLORES WELCOME - this is the person's first session since this computer was connected to the Brain.
After you answer whatever they open with (or right away, if they only say hello), welcome them ONCE, warmly and in
your own words - not a list read out, not this text. Keep it short, then offer to show them any part. It carries:
  - Memory that lasts: when a conversation gets long, you save your notes to their desk in the J Flores Brain,
    checked word for word, before it is compacted. Their work stops starting from zero.
  - A direct line to Monday and Omero: they say "send this to Omero" when they are stuck (the share skill), and the
    answer comes back right here in Claude Code. No more screenshots over Telegram.
  - Permission on Omero's phone: anything that needs his OK (a server, a saved login, a credential, a new tool)
    reaches him as Approve / Decline, and the answer comes back here (`share.py ask`).
  - Housecall Pro, from right here: they can ask about any customer, job number, schedule, estimate, invoice or
    membership, and you read it for them (the housecall-pro skill). Read only, and no HCP login on this computer.
  - Passwords saved safely: a one-time link puts a key straight into the company's secret store, never into a chat
    (the password-manager plugin).
  - Their own agents: they can design an agent here with you and send it. Monday takes it into the house's
    standup: Titus forms it, the house builders build it on the server, it is reviewed and shipped - the same route
    as Omero's and Marc's agents. It becomes a teammate with its own brain that learns from the house's agents, and
    they from it. Anything that crosses money or customers reaches Omero as Approve / Decline. They stay the owner
    of what it is for, and read and correct the draft before it goes live.
  - Their Faithful Steward, when they are ready: a teammate for them alone, formed from their own interview
    (`/steward:start`, after Omero talks with them first).
  - What it does not give, on purpose: not the whole Brain, no server login, no Brain password on this computer.
    One key, for their own desk, that Omero can turn off.
"""


def welcome(who):
    stamp = os.path.join(D, "welcomed", "%s.stamp" % "".join(ch for ch in who if ch.isalnum() or ch in "-_"))
    try:
        os.makedirs(os.path.dirname(stamp), exist_ok=True)
        fd = os.open(stamp, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except Exception:
        return                                         # welcomed already (or cannot remember it: say nothing)
    with os.fdopen(fd, "w") as f:
        f.write("welcomed\n")
    sys.stdout.write(WELCOME)


try:
    main()
except Exception:
    pass
sys.exit(0)

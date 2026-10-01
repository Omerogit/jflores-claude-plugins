# -*- coding: utf-8 -*-
"""keys.py - put a password, API key or token into the J Flores secret store from a person's OWN machine, without
the value ever passing through this machine, a terminal, or a chat.

It asks the Brain door (with this machine's Brain key, the one `refocus.py connect` saved) for a one-time keydrop
link. The person opens the link, pastes each value into its own box, and presses one button; the value goes from
their browser straight into the store, where it is read back and checked. Keys are saved under the person's own
name (marc-hcp-api), so nobody's key can overwrite one the house already uses. Standard library only.

    keys.py request <name> --field "Label in the vendor's words=json_key" [--field ...] --note "what it is for"
                    [--ttl MIN]          a one-time link (default 30 minutes)
    keys.py status                       your keys that landed (names, lengths, short hashes - never a value),
                                         and your links still open

Exit codes: 3 no brain connected - 5 the door refused - 6 the door did not answer -
7 a J Flores house machine (office seat, Omero's bench): use the house password-manager skill instead.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
D = os.environ.get("REFOCUS_HOME") or os.path.join(HOME, ".claude", "refocus")   # REFOCUS_HOME: tests only
CONF = os.path.join(D, "door.json")


def out(s=""):
    sys.stdout.write(s + "\n")
    sys.stdout.flush()


def house_machine():
    """The house's own machines have their own password-manager skill, which works on the server directly."""
    if os.environ.get("REFOCUS_IGNORE_HOUSE_WATCH"):
        return None                                        # tests only
    if os.environ.get("OFFICE_SEAT"):
        return "an office seat (%s)" % os.environ["OFFICE_SEAT"]
    if os.path.exists(os.path.join(HOME, ".claude", "hooks", "context_watch.py")):
        return "Omero's bench (the house context watch is installed)"
    if os.path.exists(os.path.join(HOME, ".claude", "brain.json")):
        return "a machine with a house brain.json"
    if os.path.isdir("/home/monday/office"):
        return "monday-server"
    return None


def conf():
    try:
        with open(CONF, encoding="utf-8") as f:
            c = json.load(f)
        if c.get("door") and c.get("key"):
            return c
    except (OSError, ValueError):
        pass
    out("+----------------------------------------------------------------------------+")
    out("| NO BRAIN CONNECTED ON THIS MACHINE - no key link can be made.              |")
    out("| Ask Omero for your Brain link, click it, and press Enter in Claude Code.   |")
    out("+----------------------------------------------------------------------------+")
    sys.exit(3)


def door(method, path, body=None):
    c = conf()
    h = {"Accept": "application/json", "User-Agent": "refocus-plugin/1.2", "Authorization": "Bearer " + c["key"]}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(c["door"] + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=150) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            b = json.loads(e.read().decode("utf-8") or "{}")
        except ValueError:
            b = {"error": "HTTP %d" % e.code}
        if e.code == 401:
            out("keys: the Brain does not accept this machine's key (%s). Ask Omero for a new link." % b.get("error"))
            sys.exit(3)
        out("keys: refused: %s" % b.get("error", "HTTP %d" % e.code))
        sys.exit(5)
    except Exception as e:
        out("keys: the Brain door did not answer (%s: %s). Nothing was made." % (type(e).__name__, str(e)[:160]))
        sys.exit(6)


def cmd_request(a):
    fields = []
    for spec in a.field:
        if "=" not in spec:
            sys.exit("keys: --field must be 'Label shown to the person=json_key', got %r" % spec)
        label, key = spec.rsplit("=", 1)
        fields.append({"label": label.strip(), "key": key.strip()})
    b = door("POST", "/v1/keys/request", {"name": a.name, "fields": fields, "note": a.note, "ttl": a.ttl})
    out("KEY LINK  %s" % b["link"])
    out("  saves as   %s" % b["secret"])
    out("  boxes      %s" % ", ".join(b.get("boxes") or []))
    out("  works once, for %d minutes. Opening it does not use it up; pressing its button does." % a.ttl)


def cmd_status(a):
    b = door("GET", "/v1/keys")
    out("KEYS for %s (every name starts %s)" % (b["person"], b["prefix"]))
    if not b["landed"] and not b["waiting"]:
        out("  none yet")
    for x in b["landed"]:
        out("  saved    %-30s v%-3s %-8s check=%s  %s  %s" % (
            x["secret"], x.get("version"), x.get("action"), x.get("verify"), x.get("at"),
            "  ".join("%s(%s chars, %s)" % (f["key"], f["len"], f["sha12"]) for f in x.get("boxes") or [])))
    for x in b["waiting"]:
        out("  waiting  %-30s boxes: %s  (link open until %s)" % (x["secret"], ", ".join(x["boxes"]), x["expires"]))


def main():
    ap = argparse.ArgumentParser(description="a one-time link to put a key into the J Flores secret store")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("request")
    r.add_argument("name")
    r.add_argument("--field", action="append", default=[], required=True)
    r.add_argument("--note", default="")
    r.add_argument("--ttl", type=int, default=30)
    sub.add_parser("status")
    a = ap.parse_args()
    why = house_machine()
    if why:
        out("HOUSE MACHINE - %s. Use the house skill `password-manager` (not `refocus:password-manager`)." % why)
        sys.exit(7)
    {"request": cmd_request, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
# One refocus copy runs, never two (refocus 1.7.2-1.7.3, 2026-11-09). refocus moved into jflores-house-plugins, which the
# Claude Team org syncs to every member. A laptop that also added the jflores-claude-plugins marketplace would run
# each hook twice against the same ~/.claude/refocus state: two refocus asks, two share answers, two welcomes. The
# marketplace copy steps aside when the org-synced copy is installed and not switched off; the org copy never does.
import glob
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def yields_to_org_copy():
    if os.environ.get("REFOCUS_ONE_COPY_OFF") or os.environ.get("REFOCUS_IGNORE_HOUSE_WATCH"):
        return False                                      # tests only: drive this checkout's copy
    if "/plugins/synced/" in ROOT.replace("\\", "/"):
        return False
    home = os.path.join(os.path.expanduser("~"), ".claude")
    try:
        on = json.load(io.open(os.path.join(home, "settings.json"), encoding="utf-8")).get("enabledPlugins") or {}
    except Exception:
        on = {}
    if on.get("refocus@synced") is False:
        return False
    # The org manifest must list it: a folder left from an earlier sync generation is not an installed copy.
    for man in glob.glob(os.path.join(home, "plugins", "synced", "*", "manifest.json")):
        try:
            listed = any(p.get("name") == "refocus" for p in json.load(io.open(man, encoding="utf-8"))["plugins"])
        except Exception:
            listed = False
        if listed and glob.glob(os.path.join(os.path.dirname(man), "refocus*", ".claude-plugin", "plugin.json")):
            return True
    return False

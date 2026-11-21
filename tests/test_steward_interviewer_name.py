"""steward 1.1.10: the interviewer says who is asking (Haru's interview, 2026-11-18, said it was plain "Claude").

Offline. Checks the three places the interviewer learns who it is: the welcome it prints word for word, the skill's
conversation rules, and the line the hook adds on every recorded turn - and that each keeps the honest answer (it
does run on Claude) instead of hiding it.
"""
import io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(ROOT, "plugins", "steward")
fails = 0


def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  <- " + str(detail)[:200]))
    fails += 0 if ok else 1


def read(*p):
    return io.open(os.path.join(ST, *p), encoding="utf-8").read()


welcome = read("skills", "start", "WELCOME.md")
first = welcome.split("\n", 1)[0]
check("the welcome's first line says who is speaking: the J Flores house interviewer",
      "J Flores house interviewer" in first, first)
check("the welcome names Titus as the one it is here for", "Titus" in first, first)
check("the welcome never introduces itself as Claude", "Claude" not in first, first)
check("the welcome still ends on the first question", welcome.rstrip().endswith("What did your day actually look like?"))

skill = read("skills", "start", "SKILL.md")
check("the skill tells it to introduce itself as the house interviewer, never plain Claude",
      "J Flores house interviewer" in skill and 'never as plain "Claude"' in skill)
check("the skill keeps the honest answer: asked, it says it runs on Claude, and never denies it",
      re.search(r"say yes, honestly", skill) and "Never deny it" in skill)

hook = read("scripts", "hook.py")
m = re.search(r'"\[steward\] The person\'s words are recorded.*?% \(r\["n"\], r\["n"\]\)', hook, re.S)
line = m.group(0) if m else ""
check("each recorded turn's line names the J Flores house interviewer, here for Titus",
      "J Flores house interviewer" in line and "Titus" in line, line)
check("each recorded turn's line keeps it honest about running on Claude", "honestly you run on Claude" in line, line)

ver = read(".claude-plugin", "plugin.json")
import re as _re
_v = tuple(int(x) for x in (_re.search(r'"version": "(\d+)\.(\d+)\.(\d+)"', ver) or _re.search("()()()", "")).groups() if x)
check("plugin.json is 1.1.10 or later (1.1.11 added the one thread)", _v >= (1, 1, 10), str(_v))
print("%d failed" % fails)
sys.exit(1 if fails else 0)

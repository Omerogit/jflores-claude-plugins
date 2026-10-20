"""Every hook command in every plugin, run through every shell Claude Code may run it in. No network, no Brain.
    python tests/test_hook_launch.py
Claude Code runs a plugin hook through `sh -c` (Mac, Linux), Git Bash (Windows), or PowerShell (Windows without Git
Bash), and puts ${CLAUDE_PLUGIN_ROOT} into the command with forward slashes (plugins manifest reference). Until 2026-10-19
every hook began `sh ".../py.sh"`, which PowerShell cannot run, so on a laptop with no Git no hook of ours ever ran
(DECISION-STEWARD-LAPTOP-STANDUP-2026-10-19-01). Each plugin is copied into a folder whose name has a space, its hook
scripts are swapped for probes, and each hooks.json command must reach the right probe, with stdin, in every shell found.
The MUST-FAIL case proves the PowerShell check bites: the extensionless form tried first ran nothing there."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS = [p for p in ("steward", "refocus") if os.path.isfile(os.path.join(ROOT, "plugins", p, "hooks", "hooks.json"))]
fails = []
PROBE = 'import sys, os\nprint("PROBE-RAN %s " + repr(sys.stdin.read()))\n'


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:600]), flush=True)
    if not cond:
        fails.append(name)


def shells():
    """(label, argv-prefix) for every shell Claude Code could use on this machine."""
    out = []
    if os.name == "nt":
        ps = shutil.which("powershell") or shutil.which("pwsh")
        if ps:
            out.append(("powershell", [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]))
        for cand in (os.environ.get("CLAUDE_CODE_GIT_BASH_PATH"), r"C:\Program Files\Git\bin\bash.exe",
                     shutil.which("bash")):
            if cand and os.path.isfile(cand) and "system32" not in cand.lower():
                out.append(("git-bash", [cand, "-c"]))
                break
    else:
        out.append(("sh", ["/bin/sh", "-c"]))
    return out


def commands(hooks_json):
    for event, groups in json.load(open(hooks_json, encoding="utf-8"))["hooks"].items():
        for g in groups:
            for h in g["hooks"]:
                if h.get("type") == "command":
                    yield event, h["command"]


def target(cmd, scripts):
    """The hook script a command means: the stub's hook_target, or a bare .py argument on the command line."""
    words = cmd.replace('"', " ").split()
    py = [w for w in words if w.endswith(".py")]
    if py:
        return py[-1]
    stub = os.path.join(scripts, os.path.basename(words[-1]))
    text = open(stub, encoding="utf-8").read() if os.path.isfile(stub) else ""
    return text.split("hook_target=")[1].split(";")[0] if "hook_target=" in text else "?"


def run(shell, cmd, root, env, stdin):
    line = cmd.replace("${CLAUDE_PLUGIN_ROOT}", root)
    e = dict(env, CLAUDE_PLUGIN_ROOT=root)
    return subprocess.run(shell + [line], input=stdin, env=e, capture_output=True, text=True, timeout=60)


tmp = tempfile.mkdtemp(prefix="hook launch ")
SH = shells()
check("found at least one shell to test", bool(SH), SH)
for plug in PLUGINS:
    src = os.path.join(ROOT, "plugins", plug)
    root = os.path.join(tmp, "plugin " + plug)
    shutil.copytree(src, root)
    root_fwd = root.replace("\\", "/")
    scripts = os.path.join(root, "scripts")
    cmds = list(commands(os.path.join(root, "hooks", "hooks.json")))
    check(plug + ": hooks.json has command hooks", bool(cmds), cmds)
    for event, cmd in cmds:
        check(plug + " " + event + ": no `sh` in front (PowerShell has none)", not cmd.lstrip().startswith("sh "), cmd)
        check(plug + " " + event + ": the plugin path is quoted (spaces in user names)",
              '"${CLAUDE_PLUGIN_ROOT}' in cmd, cmd)
    for name in os.listdir(scripts):
        if name.endswith(".py"):
            open(os.path.join(scripts, name), "w", newline="\n").write(PROBE % name)
    for label, shell in SH:
        for event, cmd in cmds:
            want = target(cmd, scripts)
            r = run(shell, cmd, root_fwd, os.environ, '{"hook_event_name": "%s"}' % event)
            check("%s %s via %s: reaches %s with its stdin" % (plug, event, label, want),
                  ("PROBE-RAN %s " % want) in r.stdout and event in r.stdout, r.stdout + r.stderr)
    # No working Python: one plain notice a day, never a failure.
    if os.name == "nt":
        sysroot = os.environ.get("SystemRoot", r"C:\Windows")
        nopath = os.pathsep.join([os.path.join(sysroot, "System32"), sysroot,
                                  os.path.join(sysroot, "System32", "WindowsPowerShell", "v1.0")])
        ps = [s for l, s in SH if l == "powershell"]
        if ps:
            home = os.path.join(tmp, "home " + plug)
            os.makedirs(home)
            e2 = dict(os.environ, PATH=nopath, USERPROFILE=home)
            r1 = run(ps[0], cmds[0][1], root_fwd, e2, "{}")
            r2 = run(ps[0], cmds[0][1], root_fwd, e2, "{}")
            check(plug + " no Python (PowerShell): one plain notice", "no working Python 3" in r1.stdout, r1.stdout + r1.stderr)
            check(plug + " no Python (PowerShell): not repeated the same day", "no working Python 3" not in r2.stdout, r2.stdout)
    else:
        nopy = os.path.join(tmp, "nopy " + plug)
        os.makedirs(nopy)
        for tool in ("dirname", "date", "mkdir", "sh"):
            p = shutil.which(tool)
            if p:
                os.symlink(p, os.path.join(nopy, tool))
        e2 = dict(os.environ, PATH=nopy, HOME=os.path.join(tmp, "home " + plug))
        shell = [os.path.join(nopy, "sh"), "-c"]
        r1 = run(shell, cmds[0][1], root_fwd, e2, "{}")
        r2 = run(shell, cmds[0][1], root_fwd, e2, "{}")
        check(plug + " no Python (sh): one plain notice", "no working Python 3" in r1.stdout and r1.returncode == 0,
              r1.stdout + r1.stderr)
        check(plug + " no Python (sh): not repeated the same day", r2.stdout == "", r2.stdout)

# MUST-FAIL: the bare extensionless launcher (6a6053c) reached nothing under PowerShell. If this ever "passes",
# the PowerShell check above is no longer testing what it claims to.
ps = [s for l, s in SH if l == "powershell"]
if ps and PLUGINS:
    root = tempfile.mkdtemp(prefix="hooklaunchbare")     # no space here: the form must fail on its own, not on a space
    scripts = os.path.join(root, "scripts")
    os.makedirs(scripts)
    open(os.path.join(scripts, "bare"), "w", newline="\n").write("#!/bin/sh\necho BARE-RAN\n")
    open(os.path.join(scripts, "bare.cmd"), "w", newline="\n").write("@echo BARE-RAN\n")
    r = run(ps[0], "${CLAUDE_PLUGIN_ROOT}/scripts/bare x", root.replace("\\", "/"), os.environ, "{}")
    check("MUST-FAIL holds: PowerShell ran nothing for the bare extensionless form", "BARE-RAN" not in r.stdout,
          r.stdout + r.stderr)
    shutil.rmtree(root, ignore_errors=True)

shutil.rmtree(tmp, ignore_errors=True)
print("\n%d FAILED" % len(fails) if fails else "\nALL PASS")
sys.exit(1 if fails else 0)

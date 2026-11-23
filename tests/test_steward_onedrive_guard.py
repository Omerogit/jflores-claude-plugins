# -*- coding: utf-8 -*-
"""The steward must never crawl a OneDrive folder (steward 1.1.15, 2026-11-23). On 2026-11-22 a steward's search walked
Omar's local OneDrive; Files On-Demand downloads every cloud-only file a search reads, and his disk began to fill.
This runs the PreToolUse guard (scripts/onedrive_guard.py) the way Claude Code does - an event on stdin - against
throwaway folders, with HOME / USERPROFILE / OneDrive pointed at them. Offline; nothing touches this machine's files.

    python tests/test_steward_onedrive_guard.py
Not covered, and said so: no live Windows OneDrive with cloud-only placeholders was run.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(REPO, "plugins", "steward")
GUARD = os.path.join(ST, "scripts", "onedrive_guard.py")
fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -- " + str(detail)[:600]), flush=True)
    if not cond:
        fails.append(name)


def mk():
    root = tempfile.mkdtemp(prefix="od_guard_")
    home = os.path.join(root, "Users", "omar")
    od = os.path.join(home, "OneDrive - Acme")
    cloud = os.path.join(root, "Cloud", "Work")                  # a OneDrive root whose name does not say OneDrive
    proj = os.path.join(root, "Projects", "shop")
    for d in (od, cloud, proj, os.path.join(od, "Docs")):
        os.makedirs(d)
    for f in (os.path.join(od, "Docs", "plan.docx"), os.path.join(od, "notes.txt"), os.path.join(cloud, "a.txt"),
              os.path.join(proj, "main.py")):
        with open(f, "w") as fh:
            fh.write("x")
    try:      # 1.1.20: a link into OneDrive and one into a project folder (skipped where links cannot be made)
        os.symlink(od, os.path.join(root, "lnk"))
        os.symlink(proj, os.path.join(root, "plnk"))
    except (OSError, NotImplementedError):
        pass
    return root, home, od, cloud, proj


def run(script, ev, home, od_env, cwd):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": home, "USERPROFILE": home}
    env.update(od_env)
    ev = dict(ev, hook_event_name="PreToolUse", cwd=cwd)
    p = subprocess.run([sys.executable, script], input=json.dumps(ev).encode(), capture_output=True, env=env, timeout=30)
    out = p.stdout.decode("utf-8", "replace").strip()
    denied = False
    if out:
        try:
            denied = json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"
        except Exception:
            denied = False
    return p.returncode, denied, out


def bash(c):
    return {"tool_name": "Bash", "tool_input": {"command": c}}


def ps(c):
    return {"tool_name": "PowerShell", "tool_input": {"command": c}}


def nest(inner, n):
    for _ in range(n):
        inner = 'bash -c "%s"' % inner.replace("\\", "\\\\").replace('"', '\\"')
    return inner


def fixtures(root, home, od, cloud, proj):
    """(label, event, cwd, must_refuse). Paths use forward slashes where a shell would; the guard folds both."""
    docs = od + "/Docs"
    return [
        ("Grep path in OneDrive", {"tool_name": "Grep", "tool_input": {"pattern": "x", "path": od}}, proj, True),
        ("Grep path in a OneDrive subfolder", {"tool_name": "Grep", "tool_input": {"pattern": "x", "path": docs}}, proj, True),
        ("Grep with no path, cwd inside OneDrive", {"tool_name": "Grep", "tool_input": {"pattern": "x"}}, docs, True),
        ("Grep rooted at the home folder", {"tool_name": "Grep", "tool_input": {"pattern": "x", "path": home}}, proj, True),
        ("Grep rooted above the home folder (Users)", {"tool_name": "Grep", "tool_input": {"pattern": "x", "path": os.path.dirname(home)}}, proj, True),
        ("Grep rooted at the OneDrive named by the env var only", {"tool_name": "Grep", "tool_input": {"pattern": "x", "path": cloud}}, proj, True),
        ("Glob path in OneDrive", {"tool_name": "Glob", "tool_input": {"pattern": "**/*.docx", "path": od}}, proj, True),
        ("Glob pattern with an absolute OneDrive prefix", {"tool_name": "Glob", "tool_input": {"pattern": docs + "/**/*"}}, proj, True),
        ("Glob in the home folder", {"tool_name": "Glob", "tool_input": {"pattern": "**/*.docx", "path": home}}, proj, True),
        ("rg in OneDrive", bash("rg budget '%s'" % od), proj, True),
        ("rg with no path from a OneDrive cwd", bash("rg budget"), od, True),
        ("grep -r in OneDrive", bash("grep -rn budget '%s'" % docs), proj, True),
        ("grep -R in OneDrive (capital R)", bash("grep -R budget %s" % docs), proj, True),
        ("grep --recursive in OneDrive", bash("grep --recursive budget %s" % docs), proj, True),
        ("find in OneDrive", bash("find '%s' -name '*.docx'" % od), proj, True),
        ("find from the home folder", bash("find %s -name '*.docx'" % home), proj, True),
        ("find from ~", bash("find ~ -name '*.docx'"), proj, True),
        ("ls -R in OneDrive", bash("ls -R '%s'" % od), proj, True),
        ("tree in OneDrive", bash("tree '%s'" % od), proj, True),
        ("du in OneDrive", bash("du -sh '%s'" % od), proj, True),
        ("cd into OneDrive then rg", bash("cd '%s' && rg budget" % od), proj, True),
        ("variable $HOME search", bash("grep -r budget $HOME"), proj, True),
        ("variable $env:OneDrive Get-ChildItem -Recurse", ps("Get-ChildItem -Path $env:OneDrive -Recurse"), proj, True),
        ("Get-ChildItem -Recurse in OneDrive", ps("Get-ChildItem -Recurse -Path '%s'" % od), proj, True),
        ("gci -r in OneDrive", ps("gci '%s' -r -Filter *.docx" % od), proj, True),
        ("Get-ChildItem -Recurse from the home folder", ps("Get-ChildItem -Recurse %s" % home), proj, True),
        ("Get-ChildItem -Recurse with %USERPROFILE%", ps("Get-ChildItem -Recurse -Path $env:USERPROFILE"), proj, True),
        ("Select-String over a OneDrive wildcard", ps("Select-String -Path '%s/*.txt' -Pattern budget" % od), proj, True),
        ("Select-String over a OneDrive folder tree", ps("Get-ChildItem '%s' -Recurse | Select-String budget" % od), proj, True),
        ("findstr /s in OneDrive", bash("findstr /s /i budget %s/*.*" % od), proj, True),
        ("cat of a OneDrive wildcard", bash("cat '%s'/*.txt" % od), proj, True),
        ("python os.walk over OneDrive", bash("python3 -c \"import os; [print(r) for r,d,f in os.walk('%s')]\"" % od), proj, True),
        ("dir /s in OneDrive", ps("dir /s '%s'" % od), proj, True),
        # --- 1.1.16: the shapes Nathan and Shallum found slipping through 1.1.15
        ("grep with a OneDrive wildcard, no -r", bash("grep foo '%s'/*" % od), proj, True),
        ("grep with an unquoted OneDrive* wildcard", bash("grep foo %s/Onedrive*/*" % os.path.dirname(od)), proj, True),
        ("powershell -Command wrapping Get-ChildItem -Recurse from home", bash('powershell -Command "Get-ChildItem -Recurse"'), home, True),
        ("powershell -Command wrapping gci -r with a OneDrive path", bash('powershell -Command "gci \'%s\' -r"' % od), proj, True),
        ("pwsh -c wrapping Select-String", bash("pwsh -c 'Select-String budget %s/*.txt'" % od), proj, True),
        ("bash -c wrapping grep -r", bash("bash -c 'grep -r budget %s'" % od), proj, True),
        ("cp -r out of OneDrive", bash("cp -r '%s' /tmp/x" % od), proj, True),
        ("cp with a OneDrive wildcard", bash("cp '%s'/*.txt /tmp/x" % od), proj, True),
        ("rsync from OneDrive", bash("rsync -a '%s/' /tmp/x/" % od), proj, True),
        ("robocopy from OneDrive", bash("robocopy '%s' D:/backup" % od), proj, True),
        ("xcopy /s from OneDrive", bash("xcopy /s '%s' D:/backup" % od), proj, True),
        ("Copy-Item -Recurse from OneDrive", ps("Copy-Item -Recurse '%s' D:/backup" % od), proj, True),
        ("tar of OneDrive", bash("tar czf /tmp/x.tgz '%s'" % od), proj, True),
        ("a search inside $(...)", bash("echo $(grep -r budget '%s')" % od), proj, True),
        ("a search inside backticks", bash("echo `find '%s' -name x`" % od), proj, True),
        ("ls | xargs grep in OneDrive", bash("ls '%s' | xargs grep budget" % od), proj, True),
        ("find | xargs cat from the home folder", bash("find %s -name '*.txt' | xargs cat" % home), proj, True),
        ("ls | xargs grep with no path from a OneDrive cwd", bash("ls | xargs grep budget"), od, True),
        ("Select-String over a wildcard folder under home", ps("Select-String -Path '%s/*/*.txt' -Pattern budget" % home), proj, True),
        ("grep over a wildcard folder under home", bash("grep foo %s/*/*.txt" % home), proj, True),
        ("WSL /mnt/c/Users/omar recursive search", bash("grep -r budget /mnt/c/Users/omar"), proj, True),
        # --- 1.1.19: Shallum's remaining gaps (Git Bash drive and filesystem roots; a wildcard one level under home)
        ("find over the Git Bash drive /c", bash("find /c -name x"), proj, True),
        ("rg over /c, no trailing slash", bash("rg foo /c"), proj, True),
        ("find over the filesystem root", bash("find / -name x"), proj, True),
        ("grep -r over the filesystem root", bash("grep -r foo /"), proj, True),
        ("du over a wildcard one level under home", bash("du -sh %s/*" % home), proj, True),
        ("rg over a wildcard one level under home", bash("rg budget %s/*" % home), proj, True),
        ("grep -r over a wildcard one level under home", bash("grep -r budget %s/*" % home), proj, True),
        ("cp -r of a wildcard one level under home", bash("cp -r %s/* /tmp/x" % home), proj, True),
        ("CONTROL ls of a wildcard one level under home (names only)", bash("ls %s/*" % home), proj, False),
        ("CONTROL grep (no -r) of a wildcard one level under home", bash("grep budget %s/*" % home), proj, False),
        ("CONTROL du of a project wildcard", bash("du -sh %s/*" % proj), proj, False),
        # --- 1.1.20: the edges Nathan and Shallum named after 1.1.19
        ("git -C a OneDrive folder grep", bash("git -C '%s' grep budget" % od), proj, True),
        ("git -C a OneDrive* wildcard grep", bash("git -C %s/OneDrive* grep budget" % home), proj, True),
        ("git grep run from inside OneDrive", bash("git grep budget"), od, True),
        ("git -C the home folder ls-files", bash("git -C %s ls-files" % home), proj, True),
        ("find over a symlink that leads into OneDrive", bash("find %s/lnk/ -name x" % root), proj, True),
        ("grep -r over a symlink that leads into OneDrive", bash("grep -r budget %s/lnk" % root), proj, True),
        ("xargs -a /dev/null find from home", bash("xargs -a /dev/null find %s" % home), proj, True),
        ("xargs find over OneDrive as the first command", bash("xargs find '%s'" % od), proj, True),
        ("git -C OneDrive with -c k=v before the subcommand", bash("git -C '%s' -c core.x=1 grep budget" % od), proj, True),
        ("git -c k=v -C OneDrive grep", bash("git -c core.x=1 -C '%s' grep budget" % od), proj, True),
        ("git --git-dir=<OneDrive>/.git grep", bash("git --git-dir='%s/.git' grep budget" % od), proj, True),
        ("git --git-dir <OneDrive>/.git (separate value) grep", bash("git --git-dir '%s/.git' grep budget" % od), proj, True),
        ("git --work-tree=<OneDrive> grep", bash("git --work-tree='%s' grep budget" % od), proj, True),
        ("CONTROL git -c k=v on a project grep", bash("git -c core.x=1 -C '%s' grep budget" % proj), proj, False),
        ("CONTROL git --git-dir on a project grep", bash("git --git-dir='%s/.git' grep budget" % proj), proj, False),
        ("CONTROL git -C a project grep", bash("git -C '%s' grep budget" % proj), proj, False),
        ("CONTROL git status inside OneDrive", bash("git status"), od, False),
        ("CONTROL xargs over a project folder", bash("xargs -a /dev/null find '%s'" % proj), proj, False),
        ("CONTROL a symlink to a project folder", bash("find %s/plnk/ -name x" % root), proj, False),
        # --- 1.1.21: the five shapes found after 1.1.20 (unquoted wrapper args, copytree, deep nesting, a variable holding the path)
        ("cmd /c dir /s of home, unquoted", bash("cmd /c dir /s %s" % home), proj, True),
        ("cmd /c findstr /s over home wildcard, unquoted", bash("cmd /c findstr /s budget %s\\*" % home), proj, True),
        ("wsl grep -r over /mnt/c/Users/omar, unquoted", bash("wsl grep -r budget /mnt/c/Users/omar"), proj, True),
        ("wsl -d Ubuntu grep -r, unquoted", bash("wsl -d Ubuntu grep -r budget /mnt/c/Users/omar"), proj, True),
        ("python -c shutil.copytree of OneDrive", bash("python -c \"import shutil; shutil.copytree('%s','D:/x')\"" % od), proj, True),
        ("bash -c nested ten deep around a home search", bash(nest("grep -r budget %s" % home, 10)), proj, True),
        ("a variable holding OneDrive, then grep -r \"$D\"", bash("D='%s'; grep -r budget \"$D\"" % od), proj, True),
        ("a PowerShell variable holding home, then Get-ChildItem -Recurse", ps("$D = '%s'; Get-ChildItem -Recurse $D" % home), proj, True),
        ("CONTROL cmd /c dir of one project folder", bash("cmd /c dir %s" % proj), proj, False),
        ("CONTROL wsl ls of a project folder", bash("wsl ls %s" % proj), proj, False),
        ("CONTROL wsl grep of one named OneDrive file", bash("wsl grep budget '%s/notes.txt'" % od), proj, False),
        ("CONTROL nested ten deep around a project grep", bash(nest("grep -r budget %s" % proj, 10)), proj, False),
        ("CONTROL a variable holding a project folder", bash("D='%s'; grep -r budget \"$D\"" % proj), proj, False),
        ("CONTROL shutil.copytree of a project folder", bash("python -c \"import shutil; shutil.copytree('%s','/tmp/y')\"" % proj), proj, False),
        ("a braced variable holding OneDrive, grep -r ${D}", bash("D='%s'; grep -r budget ${D}" % od), proj, True),
        ("B=$A after A=<OneDrive>, grep -r $B", bash("A='%s'; B=$A; grep -r budget $B" % od), proj, True),
        ("B=${A} after A=home, find $B", bash("A='%s'; B=${A}; find $B -name x" % home), proj, True),
        ("wsl --cd <OneDrive> grep -r .", bash("wsl --cd '%s' grep -r budget ." % od), proj, True),
        ("wsl --cd=<home> grep -r .", bash("wsl --cd=%s grep -r budget ." % home), proj, True),
        ("a variable inside a wrapper's escaped quotes", bash('D=\'%s\'; bash -c "grep -r budget \\"$D\\""' % od), proj, True),
        ("B=$(echo $A) after A=<OneDrive>, grep -r $B", bash("A='%s'; B=$(echo $A); grep -r budget $B" % od), proj, True),
        ("B=`echo home` then find $B", bash("B=`echo %s`; find $B -name x" % home), proj, True),
        ("wsl --cd=\"<OneDrive>\" grep -r .", bash('wsl --cd="%s" grep -r budget .' % od), proj, True),
        ("wsl --cd='<OneDrive>' grep -r .", bash("wsl --cd='%s' grep -r budget ." % od), proj, True),
        ("wsl \"--cd=<OneDrive>\" grep -r .", bash('wsl "--cd=%s" grep -r budget .' % od), proj, True),
        ("${D:-default} with D holding OneDrive", bash("D='%s'; grep -r budget ${D:-/tmp}" % od), proj, True),
        ("${U:-<OneDrive>} default naming OneDrive", bash("grep -r budget ${U:-'%s'}" % od), proj, True),
        ("local D=<OneDrive>; grep -r $D", bash("local D='%s'; grep -r budget $D" % od), proj, True),
        ("declare -x D=<OneDrive>; grep -r $D", bash("declare -x D='%s'; grep -r budget $D" % od), proj, True),
        ("D=$(echo <OneDrive>); grep -r $D", bash("D=$(echo '%s'); grep -r budget $D" % od), proj, True),
        ("a variable inside a double-quoted os.walk one-liner", bash("D='%s'; python3 -c \"import os;os.walk('$D')\"" % od), proj, True),
        ("a braced variable inside a double-quoted os.walk one-liner", bash("D='%s'; python3 -c \"import os;os.walk('${D}')\"" % od), proj, True),
        ("CONTROL wsl --cd=\"<project>\" grep -r .", bash('wsl --cd="%s" grep -r budget .' % proj), proj, False),
        ("CONTROL ${D:-default} on a project", bash("D='%s'; grep -r budget ${D:-%s}" % (proj, proj)), proj, False),
        ("CONTROL local D=<project>", bash("local D='%s'; grep -r budget $D" % proj), proj, False),
        ("CONTROL D=$(echo <project>)", bash("D=$(echo '%s'); grep -r budget $D" % proj), proj, False),
        ("CONTROL a variable inside an os.walk one-liner on a project", bash("D='%s'; python3 -c \"import os;os.walk('$D')\"" % proj), proj, False),
        ("CONTROL B=$(echo $A) after A=<project>", bash("A='%s'; B=$(echo $A); grep -r budget $B" % proj), proj, False),
        ("CONTROL B=$A after A=<project>", bash("A='%s'; B=$A; grep -r budget $B" % proj), proj, False),
        ("CONTROL wsl --cd <project> grep -r .", bash("wsl --cd '%s' grep -r budget ." % proj), proj, False),
        ("CONTROL a braced variable holding a project", bash("D='%s'; grep -r budget ${D}" % proj), proj, False),
        # --- controls: these must still pass
        ("CONTROL grep with a wildcard in a project folder", bash("grep foo '%s'/*.py" % proj), proj, False),
        ("CONTROL powershell -Command wrapping a project listing", bash('powershell -Command "Get-ChildItem -Recurse \'%s\'"' % proj), proj, False),
        ("CONTROL bash -c wrapping a project grep", bash("bash -c 'grep -r budget %s'" % proj), proj, False),
        ("CONTROL cp -r of a project folder", bash("cp -r '%s' /tmp/x" % proj), proj, False),
        ("CONTROL cp of ONE named OneDrive file", bash("cp '%s/notes.txt' /tmp/x" % od), proj, False),
        ("CONTROL rsync of a project folder", bash("rsync -a '%s/' /tmp/x/" % proj), proj, False),
        ("CONTROL a $(...) that is harmless", bash("echo $(git rev-parse HEAD)"), proj, False),
        ("CONTROL ls | xargs grep inside a project", bash("ls '%s' | xargs grep budget" % proj), proj, False),
        ("CONTROL a wildcard on the last part under home (names only)", bash("ls %s/*.txt" % home), proj, False),
        ("CONTROL Grep in a project folder", {"tool_name": "Grep", "tool_input": {"pattern": "x", "path": proj}}, proj, False),
        ("CONTROL Grep with no path in a project cwd", {"tool_name": "Grep", "tool_input": {"pattern": "x"}}, proj, False),
        ("CONTROL Glob in a project folder", {"tool_name": "Glob", "tool_input": {"pattern": "**/*.py", "path": proj}}, proj, False),
        ("CONTROL rg in a project folder", bash("rg budget '%s'" % proj), proj, False),
        ("CONTROL find in a project folder", bash("find '%s' -name '*.py'" % proj), proj, False),
        ("CONTROL Get-ChildItem -Recurse in a project folder", ps("Get-ChildItem -Recurse -Path '%s'" % proj), proj, False),
        ("CONTROL grep -r a project folder from a OneDrive-free cwd", bash("grep -rn budget %s" % proj), proj, False),
        ("CONTROL grep of ONE named OneDrive file", bash("grep budget '%s/notes.txt'" % od), proj, False),
        ("CONTROL cat of ONE named OneDrive file", bash("cat '%s/notes.txt'" % od), proj, False),
        ("CONTROL Get-Content of ONE named OneDrive file", ps("Get-Content '%s/Docs/plan.docx'" % od), proj, False),
        ("CONTROL Grep of ONE named OneDrive file", {"tool_name": "Grep", "tool_input": {"pattern": "x", "path": od + "/notes.txt"}}, proj, False),
        ("CONTROL Glob naming ONE OneDrive file", {"tool_name": "Glob", "tool_input": {"pattern": od + "/notes.txt"}}, proj, False),
        ("CONTROL an ordinary command", bash("git status"), proj, False),
        ("CONTROL ls of the project (not recursive)", bash("ls '%s'" % proj), proj, False),
        ("CONTROL the Read tool is never touched", {"tool_name": "Read", "tool_input": {"file_path": od + "/notes.txt"}}, proj, False),
    ]


def main():
    root, home, od, cloud, proj = mk()
    try:
        env_od = {"OneDrive": od, "OneDriveCommercial": cloud}
        rows = fixtures(root, home, od, cloud, proj)
        for label, ev, cwd, want in rows:
            rc, denied, out = run(GUARD, ev, home, env_od, cwd)
            check(("REFUSES " if want else "ALLOWS ") + label, rc == 0 and denied == want, "rc=%s denied=%s out=%s" % (rc, denied, out))
        rc, denied, out = run(GUARD, rows[0][1], home, env_od, proj)
        check("the refusal tells the steward what to do instead",
              "onedrive_list" in out and "onedrive_get" in out and "one file" in out.lower(), out)
        rc, denied, out = run(GUARD, {"tool_name": "Grep", "tool_input": {"path": od}}, home, {}, proj)
        check("a OneDrive folder is caught by its name even when no OneDrive env var is set", denied, out)
        p = subprocess.run([sys.executable, GUARD], input=b"not json", capture_output=True, timeout=30)
        check("an event it cannot read is let through, quietly, exit 0", p.returncode == 0 and not p.stdout.strip())


        # ---- Windows-shaped paths, folded by the same code (a Linux test machine has no C:\ drive, so decide() is called directly)
        sys.path.insert(0, os.path.join(ST, "scripts"))
        import onedrive_guard as G
        wenv = {"USERPROFILE": r"C:\Users\omar", "OneDrive": r"C:\Users\omar\OneDrive - Acme", "OneDriveCommercial": r"C:\Users\omar\OneDrive - Acme"}
        wcwd = r"C:\Projects\shop"
        for label, ev, want in [
            ("win Grep in OneDrive", {"tool_name": "Grep", "tool_input": {"path": r"C:\Users\omar\OneDrive - Acme\Docs"}}, True),
            ("win Grep in OneDrive, other drive-letter case", {"tool_name": "Grep", "tool_input": {"path": r"c:\users\OMAR\onedrive - acme"}}, True),
            ("win Grep at C:\\Users\\omar", {"tool_name": "Grep", "tool_input": {"path": r"C:\Users\omar"}}, True),
            ("win Glob at C:\\Users", {"tool_name": "Glob", "tool_input": {"pattern": "**/*.docx", "path": r"C:\Users"}}, True),
            ("win Glob at a drive root", {"tool_name": "Glob", "tool_input": {"pattern": "*.docx", "path": "C:\\"}}, True),
            ("win Get-ChildItem -Recurse %OneDrive%", {"tool_name": "PowerShell", "tool_input": {"command": "Get-ChildItem -Recurse -Path %OneDrive%"}}, True),
            ("win cmd dir /s in OneDrive", {"tool_name": "Bash", "tool_input": {"command": r'dir /s "C:\Users\omar\OneDrive - Acme"'}}, True),
            ("win rg in OneDrive", {"tool_name": "Bash", "tool_input": {"command": r'rg budget "C:\Users\omar\OneDrive - Acme"'}}, True),
            ("win cd then Get-ChildItem -Recurse", {"tool_name": "PowerShell", "tool_input": {"command": r"cd 'C:\Users\omar\OneDrive - Acme'; Get-ChildItem -Recurse"}}, True),
            ("win WSL /mnt/c/Users/omar search", {"tool_name": "Bash", "tool_input": {"command": "grep -r budget /mnt/c/Users/omar"}}, True),
            ("win Git Bash /c/Users/omar search", {"tool_name": "Bash", "tool_input": {"command": "grep -r budget /c/Users/omar"}}, True),
            ("win powershell wrapper with gci -r on the home path", {"tool_name": "Bash", "tool_input": {"command": r'powershell -Command "gci C:\Users\omar -r"'}}, True),
            ("win Select-String -Path over a wildcard folder under home", {"tool_name": "PowerShell", "tool_input": {"command": r"Select-String -Path C:\Users\omar\*\*.txt -Pattern x"}}, True),
            ("win robocopy from OneDrive", {"tool_name": "Bash", "tool_input": {"command": r'robocopy "C:\Users\omar\OneDrive - Acme" D:\b /E'}}, True),
            ("win CONTROL Grep in a project folder", {"tool_name": "Grep", "tool_input": {"path": r"C:\Projects\shop\src"}}, False),
            ("win CONTROL Get-ChildItem -Recurse in a project folder", {"tool_name": "PowerShell", "tool_input": {"command": r"Get-ChildItem -Recurse C:\Projects\shop"}}, False),
            ("win CONTROL Get-Content of one OneDrive file", {"tool_name": "PowerShell", "tool_input": {"command": r"Get-Content 'C:\Users\omar\OneDrive - Acme\notes.txt'"}}, False),
        ]:
            got = G.decide(dict(ev, cwd=wcwd), wenv)
            check(("win REFUSES " if want else "win ALLOWS ") + label, bool(got) == want or (not want and got is None), got)

        # ---- the wiring: the hook is registered, covers all four tools, and its launcher stub exists
        hooks = json.load(open(os.path.join(ST, "hooks", "hooks.json")))["hooks"]
        pre = hooks.get("PreToolUse") or []
        check("hooks.json has a PreToolUse entry", len(pre) == 1, pre)
        if pre:
            m = pre[0].get("matcher", "")
            check("the matcher covers Grep, Glob, Bash and PowerShell, and not Read",
                  all(t in m.split("|") for t in ("Grep", "Glob", "Bash", "PowerShell")) and "Read" not in m.split("|"), m)
            cmd = pre[0]["hooks"][0]["command"]
            check("its command is the same launcher form the other hooks use", cmd == '. "${CLAUDE_PLUGIN_ROOT}/scripts/onedrive_guard.cmd"', cmd)
        stub = open(os.path.join(ST, "scripts", "onedrive_guard.cmd")).read()
        check("the launcher stub names the guard script for both shells",
              "hook_target=onedrive_guard.py" in stub and 'hook_launch.cmd" onedrive_guard.py' in stub, stub)
        ver = json.load(open(os.path.join(ST, ".claude-plugin", "plugin.json")))["version"]
        check("the plugin version is bumped past 1.1.13", tuple(int(x) for x in ver.split(".")) > (1, 1, 13), ver)
        skill = open(os.path.join(ST, "skills", "start", "SKILL.md"), encoding="utf-8").read()
        check("the steward's own instructions carry the plain-words line", "OneDrive" in skill and "onedrive_get" in skill)

        # ---- MUST-FAIL: take the protection away and the refusing fixtures must go red
        tmp = tempfile.mkdtemp(prefix="od_mut_")
        try:
            src = open(GUARD, encoding="utf-8").read()
            muts = {
                "hook removed (the guard does nothing)": "import sys\nsys.exit(0)\n",
                "env-var check dropped (OneDrive / OneDriveCommercial no longer read)":
                    src.replace('if k.lower().startswith("onedrive") and v:', 'if False and v:'),
                "the above-OneDrive rule dropped (a search of the home folder passes)":
                    src.replace("def above_onedrive(p, env):", "def above_onedrive(p, env):\n    return False"),
                "the name rule dropped (no folder is a OneDrive folder by its name)":
                    src.replace('if any(seg.startswith("onedrive") for seg in p.split("/")):', "if False:"),
                "1.1.16 wildcard-grep rule dropped": src.replace("or any(is_wild(p) for p in paths)      #", "or False      #"),
                "1.1.16 wrapper rule dropped (powershell/bash -c not unwrapped)": src.replace("if base in WRAPPERS:", "if False:"),
                "1.1.16 copy rule dropped (cp/rsync/robocopy pass)": src.replace("elif base in COPY_ALWAYS:", "elif False:").replace("elif base in COPY_FLAGGED:", "elif False:"),
                "1.1.16 $(...) rule dropped": src.replace("    if depth < 4:\n        # 1.1.16: a search inside", "    if False:\n        # 1.1.16: a search inside"),
                "1.1.16 xargs rule dropped": src.replace('if base == "xargs" and k > 0:', "if False:"),
                "1.1.16 wildcard-folder rule dropped": src.replace("or wild_descends(p, env):", ":"),
                "1.1.16 WSL path rule dropped": src.replace('if re.match(r"^/(mnt/)?[a-z](/users(/[^/]+)?)?$", p):', "if False:"),
                "1.1.19 slash-root rule dropped (find / and find /c pass)": src.replace("posix = base in POSIX_SEARCH", "posix = False"),
                "1.1.19 walking-wildcard rule dropped (du ~/* passes)": src.replace("if walks and is_wild(p):", "if False:"),
                "1.1.20 symlink rule dropped (a link into OneDrive passes)": src.replace("rp = norm(os.path.realpath(lit))", "rp = norm(lit)"),
                "1.1.20 xargs-runs-the-command rule dropped": src.replace('if base == "xargs" and depth < 8:', "if False:"),
                "1.1.20 git option-value rule dropped (-c k=v read as the subcommand)": src.replace('if a in ("-c", "--namespace", "--exec-path", "--super-prefix", "--config-env"):', "if False:"),
                "1.1.20 git --git-dir/--work-tree rule dropped": src.replace('if m2 or a in ("--git-dir", "--work-tree"):', "if False:"),
                "1.1.20 git rule dropped (git -C OneDrive grep passes)": src.replace('if sub in ("grep", "ls-files", "archive", "bundle")', "if False and sub"),
                "1.1.21 unquoted-wrapper rule dropped (cmd /c and wsl pass)": src.replace("            if rest and not (len(rest) == 1", "            if False and rest and not (len(rest) == 1"),
                "1.1.21 copytree rule dropped (a copytree one-liner passes)": src.replace("|copytree|make_archive|shutil\\.move|distutils\\.dir_util|listdir", ""),
                "1.1.21 nesting cap fails open again (past 8 wrappers passes)": src.replace('return "nested wrappers deeper than 8 levels"', "pass"),
                "1.1.21 nesting unescape dropped (escaped inner quotes unread)": src.replace("re.sub(r'\\\\([\"\\\\])', r\"\\1\", q) if", "q if False else q if"),
                "1.1.21 variable rule dropped (D=<OneDrive>; grep -r $D passes)": src.replace("env[am.group(1)] =", "_unused ="),
                "1.1.21 variable-from-variable rule dropped (B=$A not followed)": src.replace("= subst_vars(val.strip()", "= (lambda v, e: v)(val.strip()"),
                "1.1.21 command-substitution value rule dropped (B=$(echo $A) not followed)": src.replace("            if cm:      #", "            if False:      #"),
                "1.1.21 r5 quoted --cd= rule dropped (--cd=\"<OneDrive>\" passes)": src.replace('aa = a.strip("\\"\'").lower()', "aa = a.lower()"),
                "1.1.21 r5 ${D:-x} rule dropped (default-value forms unread)": src.replace("    t = braced_forms(t, env)\n", "").replace('t = braced_forms(tok.strip().strip("\\"\'"), env)', 'tok.strip().strip("\\"\'")' if False else 't = tok.strip().strip("\\"\'")'),
                "1.1.21 r5 local/declare rule dropped (local D=<OneDrive> passes)": src.replace("(?:export|local|declare|typeset|readonly)", "(?:export)"),
                "1.1.21 r5 one-liner variable rule dropped ($D inside os.walk('$D') unread)": src.replace('|\\$\\{?[A-Za-z_]\\w*\\}?[^\\s"\']*', ""),
                "1.1.21 wsl --cd rule dropped (--cd <OneDrive> not judged)": src.replace('if aa in ("--cd", "--cd=") and jj + 1 < len(args):', "if False:").replace('elif aa.startswith("--cd="):', "elif False:"),
            }
            for label, text in muts.items():
                assert text != src or label.startswith("hook removed"), label
                mp = os.path.join(tmp, "m.py")
                with open(mp, "w", encoding="utf-8") as f:
                    f.write(text)
                red = [l for l, ev, cwd, want in rows if want and not run(mp, ev, home, env_od, cwd)[1]]
                check("MUST FAIL: %s turns refusing fixtures red" % label, len(red) > 0, "no fixture noticed")
                allowed_still = [l for l, ev, cwd, want in rows if not want and run(mp, ev, home, env_od, cwd)[1]]
                check("MUST FAIL (control): %s breaks no control fixture" % label, not allowed_still, allowed_still)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("\n%s" % ("ALL PASS" if not fails else "FAILED: %d" % len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

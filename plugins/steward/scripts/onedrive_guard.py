# -*- coding: utf-8 -*-
# The steward plugin's PreToolUse guard: no search or recursive listing over a OneDrive folder.
#
# Why (steward 1.1.15, 2026-11-23; widened in 1.1.16): on Windows, OneDrive's Files On-Demand keeps most files as cloud-only placeholders,
# and READING one downloads it. On 11-22 a steward's search walked Omar's local OneDrive and began pulling the whole
# tree onto his disk; only he could stop it, by clicking into the Claude Code window. A person's steward must never do
# that again, so this hook refuses, BEFORE the tool runs:
#   - Grep and Glob whose path (or glob pattern, or working folder when no path is given) is inside a OneDrive root, or
#     above one (the home folder, C:\Users\<name>, a drive root) so the walk would descend into it;
#   - Bash and PowerShell searches or recursive listings (grep -r, rg, ag, ack, fd, find, tree, du, ls -R, dir /s,
#     findstr /s, Get-ChildItem -Recurse, Select-String over a folder or wildcard, os.walk / rglob in a one-liner)
#     rooted the same way. `cd <OneDrive>` earlier in the same command counts.
# It does NOT touch Read, and it lets a search or read of ONE named file through: that hydrates one file, which is what
# the person asked for. The refusal says what to do instead (the server's onedrive_list / onedrive_get, or ask for the
# one file by name).
#
# What a OneDrive root is: %OneDrive%, %OneDriveCommercial%, %OneDriveConsumer%, and any path with a folder whose name
# begins "OneDrive" (OneDrive, "OneDrive - Company", Mac's ~/Library/CloudStorage/OneDrive-...). Stdlib only, no door,
# no network, no state: it must be fast and must work on a laptop that has never connected anything.
#
# Failure policy: an event this file cannot read is let through (a hook that breaks every tool is worse than none), but
# the decision code itself is total: every tool call it can read gets an answer.
import json
import os
import re
import sys

REFUSAL = ("Not run: this would search or list a OneDrive folder (%s). On this laptop OneDrive keeps files in the cloud "
           "until they are read, so a search downloads every file it touches and can fill the disk (it did, on "
           "2026-11-22). Do not search, grep, glob or list recursively inside OneDrive, or from a folder above it "
           "such as the home folder. Use the server's onedrive_list and onedrive_get tools (Microsoft Graph: nothing "
           "is downloaded to this laptop), or ask the person for the one file by name. Reading ONE named file the "
           "person pointed to is fine.")

SEARCHERS = {"rg", "ripgrep", "ag", "ack", "fd", "fdfind", "find", "tree", "du", "findstr", "select-string", "sls"}
GREPS = {"grep", "egrep", "fgrep", "zgrep"}
LISTERS = {"ls", "dir", "gci", "get-childitem"}
# 1.1.16: copies and archives read (so download) every file they take. Always walk a folder:
COPY_ALWAYS = {"robocopy", "xcopy", "rsync", "zip", "7z", "7za", "tar"}
# ... and these only when recursive or given a wildcard:
COPY_FLAGGED = {"cp", "copy", "mv", "move", "scp", "copy-item", "cpi", "move-item"}
WRAPPERS = {"powershell", "pwsh", "bash", "sh", "zsh", "cmd", "wsl"}
POSIX_SEARCH = {"rg", "ripgrep", "ag", "ack", "fd", "fdfind", "find", "tree", "du"} | GREPS
READERS = {"cat", "type", "gc", "get-content", "head", "tail", "wc", "more", "less", "bat"}
SHELL_CD = {"cd", "chdir", "pushd", "set-location", "sl"}
WORD = re.compile(r"""("(?:[^"\\]|\\.)*"|'[^']*'|[^\s"';|&<>()]+)""")


def split_commands(cmd):
    """Split a command line at ; | & && || and newlines that are not inside quotes."""
    out, cur, q, i = [], [], None, 0
    while i < len(cmd):
        c = cmd[i]
        if q:
            cur.append(c)
            if c == q:
                q = None
        elif c in "\"'":
            q = c
            cur.append(c)
        elif c in ";|&\n":
            out.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    out.append("".join(cur))
    return out


RECURSE_MARK = re.compile(r"os\.walk|rglob|glob\.glob|scandir|-recurse|\*\*", re.I)


# ----------------------------------------------------------------------------- paths
def norm(p):
    """Forward slashes, no trailing slash, '.' and '..' folded; the drive letter is lower-cased and the rest keeps its
    case (a case-sensitive disk needs it to find a file); every comparison below lower-cases both sides."""
    p = (p or "").replace("\\", "/")
    drive = ""
    m = re.match(r"^([A-Za-z]:)(/.*)?$", p)
    if m:
        drive, p = m.group(1).lower(), m.group(2) or "/"
    parts = []
    for seg in p.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
            continue
        parts.append(seg)
    return drive + "/" + "/".join(parts)


def home_dirs(env):
    out = set()
    for k in ("USERPROFILE", "HOME"):
        if env.get(k):
            out.add(norm(env[k]))
    hd, hp = env.get("HOMEDRIVE"), env.get("HOMEPATH")
    if hd and hp:
        out.add(norm(hd + hp))
    try:
        out.add(norm(os.path.expanduser("~")))
    except Exception:
        pass
    return {h for h in out if h not in ("", "/")}


def onedrive_roots(env):
    out = set()
    for k, v in env.items():
        if k.lower().startswith("onedrive") and v:
            out.add(norm(v))
    return out


def expand(tok, env, cwd):
    """A path token as written -> normalised absolute path. Understands ~, %VAR%, $VAR, ${VAR}, $env:VAR. A variable
    that is not set but whose name says OneDrive stays in the path as 'onedrive' (so it still counts)."""
    t = tok.strip().strip("\"'")
    low = {k.lower(): v for k, v in env.items()}

    def sub(m):
        name = m.group(1) or m.group(2) or m.group(3) or m.group(4)
        if name.lower() in ("home", "userprofile") and not low.get(name.lower()):
            return sorted(home_dirs(env))[0] if home_dirs(env) else ""
        return low.get(name.lower(), "onedrive" if "onedrive" in name.lower() else "")
    t = re.sub(r"%([A-Za-z_][A-Za-z0-9_]*)%|\$env:([A-Za-z_][A-Za-z0-9_]*)|\$\{([A-Za-z_][A-Za-z0-9_]*)\}|"
               r"\$([A-Za-z_][A-Za-z0-9_]*)", sub, t)
    if t == "~" or t.startswith("~/") or t.startswith("~\\"):
        hs = sorted(home_dirs(env))
        t = (hs[0] if hs else "") + t[1:]
    if not t:
        return None
    if re.match(r"^([A-Za-z]:)?[/\\]", t) or re.match(r"^[A-Za-z]:", t):
        return norm(t)
    return norm((cwd or ".") + "/" + t)


def is_wild(tok):
    return any(c in tok for c in "*?[")


def inside_onedrive(p, env):
    if not p:
        return False
    p = p.lower()
    if any(seg.startswith("onedrive") for seg in p.split("/")):
        return True
    return any(p == r.lower() or p.startswith(r.lower() + "/") for r in onedrive_roots(env))


def above_onedrive(p, env):
    """A walk from p would descend into OneDrive: p is above a known root, or is the home folder or higher."""
    if not p:
        return False
    p = p.lower()
    if any(r.lower().startswith(p.rstrip("/") + "/") for r in onedrive_roots(env)):
        return True
    for h in home_dirs(env):
        h = h.lower()
        if p == h or h.startswith(p.rstrip("/") + "/"):
            return True
    if re.match(r"^([a-z]:)?/(users|home)(/[^/]+)?$", p) or re.match(r"^[a-z]:/?$", p) or p == "/":
        return True
    # 1.1.16: WSL (/mnt/c/Users/omar) and Git Bash (/c/Users/omar) spellings of the same folders
    if re.match(r"^/(mnt/)?[a-z](/users(/[^/]+)?)?$", p):
        return True
    return False


def wild_descends(p, env):
    """1.1.16: a wildcard in a folder name (not the last part) walks INTO every folder it matches, so C:/Users/omar/*/*.txt
    reaches OneDrive when C:/Users/omar is home or above it."""
    parts = p.split("/")
    for i, seg in enumerate(parts[:-1]):
        if is_wild(seg):
            prefix = "/".join(parts[:i]) or "/"
            if above_onedrive(prefix, env):
                return True
    return False


def reaches(p, env, tok="", single_ok=True):
    """Would a recursive walk or a wildcard read rooted at p touch OneDrive? A single existing file is the one allowed
    shape (it hydrates one file, which the person asked for)."""
    if p is None:
        return None
    if single_ok and not is_wild(tok) and os.path.isfile(p):
        return None
    if inside_onedrive(p, env) or above_onedrive(p, env) or wild_descends(p, env):
        return p
    return None


# ----------------------------------------------------------------------------- tools
def glob_root(pat):
    """(folder the pattern starts from, True when it has a wildcard). A pattern with no wildcard names one file."""
    lit = re.split(r"[*?\[{]", pat, 1)[0]
    if lit == pat:
        return pat, False
    lit = lit.replace("\\", "/")
    return (lit if lit.endswith("/") else lit.rsplit("/", 1)[0] if "/" in lit else ""), True


def check_grep_glob(ev, env, cwd):
    ti = ev.get("tool_input") or {}
    path = ti.get("path")
    base = expand(path, env, cwd) if path else norm(cwd)
    hit = reaches(base, env, path or "", single_ok=bool(path))
    if hit:
        return hit
    if ev.get("tool_name") == "Glob" and ti.get("pattern"):
        root, wild = glob_root(ti["pattern"])
        hit = reaches(expand(root, env, base) if root else base, env, ti["pattern"] if not wild else "*",
                      single_ok=not wild)
        if hit:
            return hit
    return None


def tokens(seg):
    return [m.group(1) for m in WORD.finditer(seg)]


def looks_like_path(t):
    t = t.strip("\"'")
    return bool(t) and (t[0] not in "-/" or re.match(r"^/[A-Za-z]:|^/(users|home|mnt|c|d)\b", t, re.I) is not None
                        or t.startswith("//")) and (re.search(r"[/\\~%$:.]", t) is not None or "*" in t) or \
        bool(re.match(r"^[/\\]", t) and len(t) > 1 and not re.match(r"^/[a-z]$", t, re.I))


SUBST = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")


def check_shell(ev, env, cwd, depth=0):
    cmd = (ev.get("tool_input") or {}).get("command") or ""
    return check_cmd(cmd, env, cwd, depth)


def check_cmd(cmd, env, cwd, depth=0):
    cur = cwd
    mentions = None
    if depth < 4:
        # 1.1.16: a search inside $(...) or backticks runs too, so judge what is inside it
        for m in SUBST.finditer(cmd):
            inner = m.group(1) or m.group(2) or ""
            hit = check_cmd(inner, env, cwd, depth + 1)
            if hit:
                return hit
    segs = split_commands(cmd)
    for k, seg in enumerate(segs):
        toks = tokens(seg)
        if not toks:
            continue
        i = 0
        while i < len(toks) and (toks[i] in ("sudo", "time", "command", "nohup", "env", "&") or re.match(r"^\w+=", toks[i])):
            i += 1
        if i >= len(toks):
            continue
        base = os.path.basename(toks[i].strip("\"'").replace("\\", "/")).lower()
        base = re.sub(r"\.(exe|cmd|ps1)$", "", base)
        args = toks[i + 1:]
        if base in SHELL_CD:
            tgt = [a for a in args if not a.startswith("-") and a.lower() not in ("/d",)]
            if tgt:
                np_ = expand(tgt[0], env, cur)
                if np_:
                    cur = np_
            continue
        if base in WRAPPERS and depth < 4:
            # 1.1.16: powershell -Command "..." / bash -c "..." / wsl ...: judge the command inside the quotes
            for a in args:
                if len(a) > 2 and a[0] in "\"'" and a[-1] == a[0]:
                    hit = check_cmd(a[1:-1], env, cur, depth + 1)
                    if hit:
                        return hit
        if base == "xargs" and k > 0:
            # 1.1.16: ls | xargs grep reads every file the left side names
            rest = [a for a in args if not a.startswith("-")]
            if rest and (os.path.basename(rest[0]).lower() in GREPS | READERS | SEARCHERS | COPY_ALWAYS | COPY_FLAGGED):
                ptoks = tokens(segs[k - 1])
                ppaths = [a for a in ptoks[1:] if not a.startswith("-") and looks_like_path(a)]
                for p in (ppaths or ["."]):
                    hit = reaches(expand(p, env, cur), env, p, single_ok=False)
                    if hit:
                        return hit
            continue
        posix = base in POSIX_SEARCH
        # 1.1.19: for the POSIX search tools "/" and "/c" are a root and a Git Bash drive, never a /s-style flag
        flags = [a for a in args if a.startswith("-") or (not posix and re.match(r"^/[A-Za-z]$", a))]
        flagstr = " ".join(flags).lower()
        paths = [a for a in args if not a.startswith("-") and (posix and (a == "/" or re.match(r"^/[A-Za-z]$", a))
                                                          or (not re.match(r"^/[A-Za-z]$", a) and looks_like_path(a)))]
        recursive = False
        walks = base in SEARCHERS or base in COPY_ALWAYS    # 1.1.19: the tool itself descends into a folder it is given
        if base in GREPS or base in COPY_FLAGGED or base in LISTERS or base == "findstr":
            walks = bool(re.search(r"(^| )-[a-zA-Z]*[rRa]|--recursive|-recurse|-d recurse|(^| )/s\b", flagstr + " ", re.I)) \
                and not (base in LISTERS and not re.search(r"-r|/s", flagstr + " ", re.I))
        if base in SEARCHERS:
            recursive = True
            if base == "findstr":
                recursive = "/s" in flagstr or any(is_wild(p) for p in paths)
            if base in ("select-string", "sls"):
                paths = [a for a in args if looks_like_path(a)] or paths
                recursive = any(is_wild(p) for p in paths) or not paths or True
        elif base in GREPS:
            recursive = bool(re.search(r"(^| )-[a-z]*r|--recursive|-d recurse|--directories=recurse", flagstr, re.I)) \
                or bool(re.search(r"(^| )-[a-z]*R", " ".join(flags))) \
                or any(is_wild(p) for p in paths)      # 1.1.16: grep foo OneDrive*/* reads every file the shell matched
        elif base in COPY_ALWAYS:
            recursive = True
        elif base in COPY_FLAGGED:
            recursive = bool(re.search(r"(^| )-[a-z]*[raR]|-recurse|(^| )/[se]\b|--recursive|--archive", flagstr + " ")) \
                or any(is_wild(p) for p in paths)
        elif base in LISTERS:
            recursive = bool(re.search(r"-r(ecurse)?\b|(^| )/s\b|(^| )-[a-z]*r", flagstr + " "))
            recursive = recursive or any(is_wild(p) for p in paths)
        elif base in READERS:
            recursive = any(is_wild(p) for p in paths)
        if not recursive:
            if looks_like_embedded(base, seg):
                mentions = mentions or embedded_hit(seg, env, cur)
            continue
        if not paths:
            hit = reaches(norm(cur), env, "", single_ok=False)
            if hit:
                return hit
            continue
        for p in paths:
            hit = reaches(expand(p, env, cur), env, p)
            if hit:
                return hit
            if walks and is_wild(p):
                # 1.1.19: du -sh ~/* , rg x C:\Users\omar\* : a walking tool follows the wildcard into OneDrive*
                ex = expand(p, env, cur)
                if ex and is_wild(ex.split("/")[-1]) and above_onedrive("/".join(ex.split("/")[:-1]) or "/", env):
                    return ex
    return mentions


def looks_like_embedded(base, seg):
    return base in ("python", "python3", "py", "node", "perl", "ruby", "powershell", "pwsh", "bash", "sh", "cmd") \
        and RECURSE_MARK.search(seg) is not None


def embedded_hit(seg, env, cur):
    """A one-liner in another language that walks a tree: refused when it names a OneDrive or home-level path."""
    for t in re.findall(r"""[A-Za-z]:[\\/][^\s"']*|~[\\/]?[^\s"']*|%[A-Za-z_]+%[^\s"']*|\$env:\w+[^\s"']*|/[^\s"']+""", seg):
        hit = reaches(expand(t, env, cur), env, t, single_ok=False)
        if hit:
            return hit
    if re.search(r"onedrive", seg, re.I) or (RECURSE_MARK.search(seg) and re.search(r"\(\s*['\"]?\.?['\"]?\s*\)|['\"]\.['\"]", seg)):
        return reaches(norm(cur), env, "", single_ok=False) or ("onedrive" if re.search(r"onedrive", seg, re.I) else None)
    return None


def decide(ev, env=None):
    """None to let the call through, else the path the refusal names."""
    env = os.environ if env is None else env
    cwd = ev.get("cwd") or os.getcwd()
    name = ev.get("tool_name")
    if name in ("Grep", "Glob"):
        return check_grep_glob(ev, env, cwd)
    if name in ("Bash", "PowerShell"):
        return check_shell(ev, env, cwd)
    return None


def main():
    try:
        ev = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except Exception:
        return
    if ev.get("hook_event_name") not in (None, "PreToolUse"):
        return
    hit = decide(ev)
    if hit:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": REFUSAL % hit}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)

#!/bin/sh
# Run one of this plugin's hook scripts with a Python 3 that actually works.
# The Windows Store puts a `python3` on PATH that is only an installer stub, so each candidate is TESTED, not
# trusted. With no working Python the hook says so once a day, plainly, and never fails silently.
# On Git Bash (Windows) `pwd -W` gives C:/Users/... - a path a Windows python.exe can open even when MSYS path
# translation is off (found 2026-09-23: /c/Users/... reached python as C:\c\Users\...). Elsewhere it fails and
# plain pwd is used.
here="$(cd "$(dirname "$0")" && (pwd -W 2>/dev/null || pwd))"
script="$here/$1"
for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1; then
    if [ "$py" = "py" ]; then
      if py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
        exec py -3 "$script"
      fi
    elif "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
      exec "$py" "$script"
    fi
  fi
done
stamp="$HOME/.claude/refocus/no-python.$(date +%Y%m%d)"
if [ ! -f "$stamp" ]; then
  mkdir -p "$HOME/.claude/refocus" 2>/dev/null && : > "$stamp" 2>/dev/null
  echo "REFOCUS PLUGIN: no working Python 3 was found on this machine, so the refocus protocol cannot run."
  echo "Tell the person once, plainly: install Python 3 (python.org), then restart Claude Code. /compact still works."
fi
exit 0

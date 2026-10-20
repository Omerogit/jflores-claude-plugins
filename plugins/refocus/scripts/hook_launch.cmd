:; # Hook launcher: one file, read by BOTH shells Claude Code may run a hook in. Each hook calls a two-line stub,
:; #   . "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.cmd"      (the stub names its script and hands over to this file)
:; # sh (Mac, Linux, Windows with Git Bash) SOURCES the stub and this file: these ":;" lines are its code, and it
:; # exits before the batch half. PowerShell (Windows without Git Bash) runs the stub as a batch file: cmd reads
:; # ":" lines as labels and skips them. The path is quoted in both, so a space in a user name is fine. No exec
:; # bit, no shebang, no argument to "." (dash, Ubuntu's sh, drops those: tested 2026-10-19).
:; # Every Python candidate is TESTED, not trusted: the Windows Store "python" is only an installer stub.
:; # On Git Bash `pwd -W` gives C:/Users/... (found 2026-09-23: /c/Users/... reached python as C:\c\Users\...).
:; # DECISION-STEWARD-LAPTOP-STANDUP-2026-10-19-01.
:; here="$(cd "${CLAUDE_PLUGIN_ROOT:-.}/scripts" && (pwd -W 2>/dev/null || pwd))"; script="$here/$hook_target"
:; for py in python3 python py; do if command -v "$py" >/dev/null 2>&1; then if [ "$py" = "py" ]; then set -- -3; else set --; fi; if "$py" "$@" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" </dev/null >/dev/null 2>&1; then exec "$py" "$@" "$script"; fi; fi; done
:; stamp="$HOME/.claude/hook-launch/no-python.$(date +%Y%m%d)"; if [ ! -f "$stamp" ]; then mkdir -p "$HOME/.claude/hook-launch" 2>/dev/null && : > "$stamp" 2>/dev/null; echo "PLUGIN HOOK: no working Python 3 was found on this machine, so this plugin cannot run. Tell the person once, plainly: install Python 3 (python.org), then restart Claude Code."; fi
:; exit 0
@echo off
setlocal
set "script=%~dp0%~1"
for %%P in (python python3) do (
  %%P -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" <nul >nul 2>nul && (
    %%P "%script%"
    exit /b
  )
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" <nul >nul 2>nul && (
  py -3 "%script%"
  exit /b
)
set "d=%DATE:/=-%"
set "d=%d: =-%"
set "stamp=%USERPROFILE%\.claude\hook-launch\no-python.%d%"
if not exist "%stamp%" (
  mkdir "%USERPROFILE%\.claude\hook-launch" >nul 2>nul
  type nul > "%stamp%" 2>nul
  echo PLUGIN HOOK: no working Python 3 was found on this machine, so this plugin cannot run. Tell the person once, plainly: install Python 3 ^(python.org^), then restart Claude Code.
)
exit /b 0

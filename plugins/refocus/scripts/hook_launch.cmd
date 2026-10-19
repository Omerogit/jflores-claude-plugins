@echo off
rem Windows half of hook_launch - see the POSIX file next to this one for the full story.
rem Reached because PowerShell/cmd resolve a bare, extensionless path by trying PATHEXT
rem entries (.cmd is one) - so the same unquoted hooks.json command line lands here.
setlocal
set "script=%~dp0%~1"
where python >nul 2>nul
if %errorlevel%==0 (
  python "%script%"
  exit /b %errorlevel%
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%script%"
  exit /b %errorlevel%
)
echo This plugin found no working Python 3, so its hook cannot run. Install Python 3 (python.org), then restart Claude Code. 1>&2
exit /b 0

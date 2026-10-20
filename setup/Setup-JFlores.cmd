@echo off
setlocal
title J Flores setup
set "JF_SELF=%~f0"
echo.
echo  Setting up Claude Code for J Flores. It can take up to 10 minutes the first time. Leave this window open.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = [IO.File]::ReadAllText($env:JF_SELF); iex $s.Substring($s.IndexOf('#' + '##PS'))"
echo.
pause
exit /b

###PS - THE ONE-CLICK SETUP for every steward and assistant laptop (2026-10-19, J Flores bench).
# DECISION-STEWARD-LAPTOP-STANDUP-2026-10-19-01, points 1, 2 and 6. One file for everyone; who the person is comes
# from their own connection file, or from a connect link the house writes into {LINK} for that person.
#   1 Claude Code  2 Git (winget, this user only)  3 Python (winget, this user only)
#   4 the J Flores plugins from GitHub, with updates on  5 the connection to the person's steward
#   6 the proof: plugins match GitHub, the real hook line runs through every shell Claude Code may use, and its
#     line reached the steward's room. DONE prints only then. Any stop names its step and, when the laptop can
#     reach the room, sends the same line to the house. Nothing a person typed is ever sent.
& {
  $Link = '{LINK}'
  $Repo = 'Omerogit/jflores-claude-plugins'
  $RepoUrl = 'https://github.com/' + $Repo + '.git'   # https, never owner/repo: that form clones over SSH, and a new laptop has no GitHub key
  $Plugins = @('steward', 'refocus', 'password-manager')
  $H = if ($env:JF_TEST_HOME) { $env:JF_TEST_HOME } else { $env:USERPROFILE }
  $CD = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $H '.claude' }
  $ProgressPreference = 'SilentlyContinue'
  try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
  try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}
  $script:Warn = @()
  $script:Conn = $null
  function Say($t, $c) { if ($c) { Write-Host $t -ForegroundColor $c } else { Write-Host $t } }
  function Step($n, $t) { Say '' $null; Say ('[{0}/6] {1}' -f $n, $t) 'Cyan' }
  function Ok($t) { Say ('      OK  ' + $t) 'Green' }
  function Note($t) { Say ('      ..  ' + $t) $null }
  function Report($t) {
    # The same plain line to the house, through the person's own room, when this laptop can reach it.
    if (-not $script:Conn) { return }
    try {
      $sid = [guid]::NewGuid().ToString('N')
      $body = @{ posts = @(@{ id = ($sid.Substring(0, 8) + '-' + $sid.Substring(8, 16)); who = 'person';
                             text = ('(On the laptop, ' + (Get-Date -Format 'HH:mm') + ', setup) ' + $t) }) } | ConvertTo-Json -Depth 5 -Compress
      [void](Invoke-RestMethod -Method Post -Uri (([string]$script:Conn.base).TrimEnd('/') + '/thread') -Body ([Text.Encoding]::UTF8.GetBytes($body)) `
        -ContentType 'application/json' -Headers @{ Authorization = 'Bearer ' + $script:Conn.token } -TimeoutSec 30)
    } catch {}
  }
  function Bad($n, $t) {
    Say ('      !!  ' + $t) 'Yellow'; Say '' $null
    Say 'It did not finish. Send a picture of this window to your steward or to Omero.' 'Yellow'
    Report ('Setup stopped at step ' + $n + ' of 6: ' + $t)
  }
  function RefreshPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
  }
  function Winget($id) {
    $wg = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $wg) { return 'winget is not on this computer' }
    $out = (& $wg.Source install --id $id -e --scope user --silent --accept-package-agreements --accept-source-agreements --disable-interactivity 2>&1 | ForEach-Object { "$_" } | Out-String)
    if ($LASTEXITCODE -ne 0 -and $out -notmatch 'already installed|No newer|No available upgrade') {
      $out = (& $wg.Source install --id $id -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity 2>&1 | ForEach-Object { "$_" } | Out-String)
    }
    RefreshPath
    if ($LASTEXITCODE -ne 0 -and $out -notmatch 'already installed|No newer|No available upgrade') {
      return (($out -split "`n" | Where-Object { $_ -match '\S' } | Select-Object -Last 1) -replace '\s+', ' ').Trim()
    }
    return $null
  }
  function GoodPython {
    foreach ($cand in @('python', 'python3', 'py')) {
      if (Get-Command $cand -ErrorAction SilentlyContinue) {
        if ($cand -eq 'py') { & py -3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>$null | Out-Null }
        else { & $cand -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>$null | Out-Null }
        if ($LASTEXITCODE -eq 0) { return $cand }
      }
    }
    return $null
  }
  function GitBash {
    # Where Claude Code finds Git Bash: CLAUDE_CODE_GIT_BASH_PATH, else next to git.exe.
    if ($env:CLAUDE_CODE_GIT_BASH_PATH -and (Test-Path $env:CLAUDE_CODE_GIT_BASH_PATH)) { return $env:CLAUDE_CODE_GIT_BASH_PATH }
    $g = Get-Command git -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $g) { return $null }
    $root = Split-Path (Split-Path $g.Source)
    foreach ($b in @((Join-Path $root 'bin\bash.exe'), (Join-Path (Split-Path $root) 'bin\bash.exe'))) { if (Test-Path $b) { return $b } }
    return $null
  }

  Step 1 'Finding Claude Code'
  $Claude = $env:JF_TEST_CLAUDE
  if (-not $Claude) {
    $cmd = Get-Command claude -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { $Claude = $cmd.Source }
  }
  if (-not $Claude) {
    $found = @()
    $roots = @((Join-Path $env:APPDATA 'Claude\claude-code'), (Join-Path $env:LOCALAPPDATA 'Claude\claude-code'))
    $roots += @(Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Packages') -Directory -Filter '*Claude*' -ErrorAction SilentlyContinue |
      ForEach-Object { Join-Path $_.FullName 'LocalCache\Roaming\Claude\claude-code' })
    foreach ($root in $roots) {
      if (Test-Path $root) {
        $found += @(Get-ChildItem -Path $root -Filter claude.exe -Recurse -ErrorAction SilentlyContinue |
          Sort-Object -Descending { $v = [version]'0.0'; [void][version]::TryParse($_.Directory.Parent.Name, [ref]$v); $v })
      }
    }
    $found += @(Get-Item (Join-Path $env:USERPROFILE '.local\bin\claude.exe') -ErrorAction SilentlyContinue)
    $found += @(Get-Item (Join-Path $env:APPDATA 'npm\claude.cmd') -ErrorAction SilentlyContinue)
    if ($found.Count -gt 0) { $Claude = $found[0].FullName }
  }
  if (-not $Claude) { Bad 1 'Claude Code was not found on this computer. Install it from claude.ai/download, sign in once, then run this file again. Nothing was changed.'; return }
  Ok $Claude
  # An existing connection lets every later stop report itself to the house.
  $tj = Join-Path $H '.claude\steward\thread.json'
  if (Test-Path $tj) { try { $script:Conn = Get-Content $tj -Raw | ConvertFrom-Json } catch {} }

  Step 2 'Git (lets updates arrive by themselves)'
  RefreshPath
  if ($env:JF_TEST_NOGIT) { Note 'test: acting as if Git could not be installed'; $script:Warn += 'Git could not be installed (test), so updates will not arrive by themselves.' }
  elseif (Get-Command git -ErrorAction SilentlyContinue) { Ok 'Git is already here' }
  else {
    Note 'installing Git for this user (no admin needed)...'
    $why = Winget 'Git.Git'
    if (Get-Command git -ErrorAction SilentlyContinue) { Ok 'Git installed' }
    else { $script:Warn += ('Git could not be installed (' + $why + '), so updates will not arrive by themselves.'); Note ('Git could not be installed: ' + $why + '. Going on without it.') }
  }
  $HasGit = [bool](Get-Command git -ErrorAction SilentlyContinue) -and -not $env:JF_TEST_NOGIT

  Step 3 'Python (the plugins run on it)'
  $Py = GoodPython
  if ($Py) { Ok ('Python is already here (' + $Py + ')') }
  else {
    Note 'installing Python 3 for this user (no admin needed)...'
    $why = Winget 'Python.Python.3.12'
    $Py = GoodPython
    if (-not $Py) {
      foreach ($p in @(Get-ChildItem (Join-Path $env:LOCALAPPDATA 'Programs\Python') -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue)) {
        if (Test-Path (Join-Path $p.FullName 'python.exe')) { $env:Path = $p.FullName + ';' + (Join-Path $p.FullName 'Scripts') + ';' + $env:Path }
      }
      $Py = GoodPython
    }
    if (-not $Py) { Bad 3 ('Python 3 could not be installed (' + $why + '). Install it from python.org, then run this file again.'); return }
    Ok ('Python installed (' + $Py + ')')
  }

  Step 4 'The J Flores plugins, from GitHub, with updates on'
  function Run($a) { $r = (& $Claude @a 2>&1 | ForEach-Object { "$_" } | Out-String).Trim(); @{ ok = ($LASTEXITCODE -eq 0); out = $r } }
  function Kind {
    try {
      $km = Get-Content (Join-Path $CD 'plugins\known_marketplaces.json') -Raw -ErrorAction Stop | ConvertFrom-Json
      $src = $km.jflores.source
      if ($src) {
        if ([string]$src.source -eq 'git' -and [string]$src.url -eq $RepoUrl) { return 'remote' }
        if ([string]$src.source -eq 'github' -and [string]$src.repo -eq $Repo) { return 'remote' }
        return [string]$src.source
      }
    } catch {}
    return 'none'
  }
  function Installed($p) {
    try {
      $ip = Get-Content (Join-Path $CD 'plugins\installed_plugins.json') -Raw -ErrorAction Stop | ConvertFrom-Json
      $e = $ip.plugins.($p + '@jflores')
      if ($e) { return [string](@($e)[0].version) }
    } catch {}
    return $null
  }
  function Bring {
    foreach ($p in $Plugins) {
      [void](Run @('plugin', 'install', ($p + '@jflores'), '-s', 'user'))
      $u = Run @('plugin', 'update', ($p + '@jflores'), '-s', 'user', '-y')
      if (-not $u.ok) { [void](Run @('plugin', 'update', ($p + '@jflores'))) }
    }
  }
  $Main = @{}
  try {
    foreach ($p in $Plugins) {
      $Main[$p] = [string](Invoke-RestMethod -Uri ('https://raw.githubusercontent.com/' + $Repo + '/main/plugins/' + $p + '/.claude-plugin/plugin.json') -TimeoutSec 60).version
    }
  } catch { Bad 4 ('GitHub did not answer (' + $_.Exception.Message + '). Check the internet connection and run this file again.'); return }
  $kind = Kind
  if ($HasGit) {
    if ($kind -ne 'remote') {
      if ($kind -ne 'none') { Note 'moving the plugins from a downloaded folder to GitHub...'; [void](Run @('plugin', 'marketplace', 'remove', 'jflores')) }
      $r = Run @('plugin', 'marketplace', 'add', $RepoUrl)
      if ((Kind) -ne 'remote') { Bad 4 ('Claude Code could not add the J Flores plugins from GitHub: ' + (($r.out -split "`n") | Select-Object -Last 1)); return }
    } else { [void](Run @('plugin', 'marketplace', 'update', 'jflores')) }
    Bring
    # Updates on: Claude Code refreshes a GitHub marketplace by itself only when autoUpdate is set for it.
    $sp = Join-Path $CD 'settings.json'
    try {
      $raw = if (Test-Path $sp) { Get-Content $sp -Raw } else { '{}' }
      if (-not $raw.Trim()) { $raw = '{}' }
      $st = $raw | ConvertFrom-Json
      $want = @{ source = @{ source = 'git'; url = $RepoUrl }; autoUpdate = $true }
      $cur = $null; if ($st.extraKnownMarketplaces) { $cur = $st.extraKnownMarketplaces.jflores }
      if (-not ($cur -and $cur.autoUpdate -eq $true -and ($cur.source.url -eq $RepoUrl -or $cur.source.repo -eq $Repo))) {
        if (Test-Path $sp) { Copy-Item $sp ($sp + '.before-jflores-setup') -Force }
        if (-not $st.extraKnownMarketplaces) { $st | Add-Member -NotePropertyName extraKnownMarketplaces -NotePropertyValue ([pscustomobject]@{}) }
        $st.extraKnownMarketplaces | Add-Member -NotePropertyName jflores -NotePropertyValue ([pscustomobject]$want) -Force
        [IO.File]::WriteAllText($sp, ($st | ConvertTo-Json -Depth 32), (New-Object Text.UTF8Encoding $false))
        $chk = (Get-Content $sp -Raw | ConvertFrom-Json).extraKnownMarketplaces.jflores
        if (-not ($chk.autoUpdate -eq $true)) { throw 'the setting did not read back' }
      }
      Ok 'updates will arrive by themselves'
    } catch { $script:Warn += ('Automatic updates could not be switched on (' + $_.Exception.Message + ').'); Note ('automatic updates could not be switched on: ' + $_.Exception.Message) }
  } else {
    # No Git: the plugins come as a zip from GitHub (they work, but updates need this file again).
    $mdir = Join-Path $H '.claude\jflores-plugins'
    $zip = Join-Path $env:TEMP ('jflores-plugins-' + [guid]::NewGuid().ToString('N') + '.zip'); $x = $zip + '.d'
    try {
      Invoke-WebRequest -UseBasicParsing -Uri ('https://codeload.github.com/' + $Repo + '/zip/refs/heads/main') -OutFile $zip
      Expand-Archive -Path $zip -DestinationPath $x -Force
      $inner = Get-ChildItem $x -Directory | Select-Object -First 1
      if (Test-Path $mdir) { Remove-Item $mdir -Recurse -Force }
      [void](New-Item -ItemType Directory -Force -Path (Split-Path $mdir)); Move-Item $inner.FullName $mdir
    } catch { Bad 4 ('The plugins did not download: ' + $_.Exception.Message); return }
    if ($kind -ne 'none') { [void](Run @('plugin', 'marketplace', 'remove', 'jflores')) }
    [void](Run @('plugin', 'marketplace', 'add', $mdir))
    Bring
    Remove-Item $x -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item $zip -Force -ErrorAction SilentlyContinue
  }
  $behind = @($Plugins | Where-Object { $v = Installed $_; -not $v -or ([version]$v -lt [version]$Main[$_]) })
  if ($behind.Count) { Bad 4 ('These plugins are not on the newest version yet: ' + ($behind -join ', ') + '.'); return }
  Ok (($Plugins | ForEach-Object { $_ + ' ' + (Installed $_) }) -join ', ')

  Step 5 'The connection to your steward'
  $connected = $false
  if ($script:Conn) {
    try {
      $u = ([string]$script:Conn.base).TrimEnd('/') + '/thread?since=' + [int]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) + '&limit=1'
      [void](Invoke-RestMethod -Uri $u -Headers @{ Authorization = 'Bearer ' + $script:Conn.token; Accept = 'application/json' } -UserAgent ('steward-plugin/' + (Installed 'steward')) -TimeoutSec 60)
      $connected = $true
    } catch { Note ('the saved connection did not answer: ' + $_.Exception.Message) }
  }
  if (-not $connected -and $Link -match '^https://') {
    $spy = Join-Path $CD ('plugins\cache\jflores\steward\' + (Installed 'steward') + '\skills\start\scripts\steward.py')
    $pa = @(); if ($Py -eq 'py') { $pa += '-3' }
    $out = (& $Py @($pa + @($spy, 'thread-connect', $Link)) 2>&1 | ForEach-Object { "$_" } | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $out -match 'CONNECTED') {
      try { $script:Conn = Get-Content $tj -Raw | ConvertFrom-Json; $connected = $true } catch {}
    } else { Bad 5 ('The connect link did not work: ' + (($out -split "`n" | Where-Object { $_ -match '\S' } | Select-Object -First 1))); return }
  }
  if (-not $connected) { Bad 5 'This laptop is not connected to your steward. Text your steward on Telegram: "send me a connect link". Open the link it sends on this laptop and double-click the file it downloads.'; return }
  $Who = ([string]$script:Conn.steward).Split('-')[-1]
  if ($Who) { $Who = $Who.Substring(0, 1).ToUpper() + $Who.Substring(1) } else { $Who = 'your steward' }
  Ok ('connected to ' + $Who)

  Step 6 ('Proving ' + $Who + '''s hooks run the way Claude Code runs them')
  $sv = Installed 'steward'
  $root = Join-Path $CD ('plugins\cache\jflores\steward\' + $sv)
  $line = [string]((Get-Content (Join-Path $root 'hooks\hooks.json') -Raw | ConvertFrom-Json).hooks.UserPromptSubmit[0].hooks[0].command)
  $line = $line.Replace('${CLAUDE_PLUGIN_ROOT}', $root.Replace('\', '/'))
  $env:CLAUDE_PLUGIN_ROOT = $root.Replace('\', '/')
  $shells = @(@{ name = 'PowerShell'; bash = $null })
  $gb = GitBash
  if ($gb) { $shells = @(@{ name = 'Git Bash'; bash = $gb }) + $shells }   # Claude Code uses Git Bash when it finds it
  $log = Join-Path $H '.claude\steward\thread\thread_client.log'
  foreach ($sh in $shells) {
    $sid = [guid]::NewGuid().ToString('N')
    $ev = @{ hook_event_name = 'UserPromptSubmit'; session_id = $sid; cwd = $H;
             prompt = ('Setup check from this laptop: plugins steward ' + $sv + ', and ' + $Who + '''s hooks run here through ' + $sh.name + '.') } | ConvertTo-Json -Compress
    if ($sh.bash) {
      $f = Join-Path $env:TEMP ('jflores-hookline-' + $sid.Substring(0, 8) + '.sh')
      [IO.File]::WriteAllText($f, $line + "`n", (New-Object Text.UTF8Encoding $false))
      $hookOut = ($ev | & $sh.bash $f 2>&1 | ForEach-Object { "$_" } | Out-String).Trim()
      Remove-Item $f -Force -ErrorAction SilentlyContinue
    } else {
      $ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
      $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($line))   # -Command would lose the quotes in PS 5.1
      $hookOut = ($ev | & $ps -NoProfile -ExecutionPolicy Bypass -EncodedCommand $enc 2>&1 | ForEach-Object { "$_" } | Out-String).Trim()
    }
    $mine = @(); if (Test-Path $log) { $mine = @(Get-Content $log -ErrorAction SilentlyContinue | Where-Object { $_ -match ('prompt ' + $sid.Substring(0, 8)) }) }
    if (-not ($mine | Where-Object { $_ -match 'posted [1-9]' })) {
      $why = if ($mine.Count) { $mine[-1] } elseif ($hookOut) { ($hookOut -split "`n")[0] } else { 'the hook left no record' }
      Bad 6 ($Who + '''s hook did not reach the room through ' + $sh.name + ': ' + $why)
      return
    }
    Ok ('through ' + $sh.name + ': a setup-check line reached ' + $Who + '''s room')
  }
  Say '' $null
  if ($script:Warn.Count) {
    Say ('DONE, with one thing left: ' + ($script:Warn -join ' ')) 'Yellow'
    Say ('Your steward works now. Close Claude Code completely and open it again.') 'Yellow'
    Report ('Setup finished, with one thing left: ' + ($script:Warn -join ' '))
  } else {
    Say ('DONE. Close Claude Code completely and open it again. ' + $Who + ' is with you there.') 'Green'
  }
  Say 'You can delete this file now.' $null
}

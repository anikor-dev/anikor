# ANI.KOR installer for Windows (run by "Install ANI.KOR.bat"; safe to run again any time).
# Installs per-user, no admin needed: Scoop -> git, uv, mpv, fzf, Nerd Font (+ Windows
# Terminal if missing) -> ANI.KOR from the latest GitHub release -> profile + shortcuts.
# Your data (MyAnimeList login, cache, settings) lives in %LOCALAPPDATA%\viu and is never
# touched by installs or updates.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Repo = 'anikor-dev/anikor'

function Say($msg) { Write-Host "  $msg" -ForegroundColor Magenta }
function Ok($msg)  { Write-Host "  [ok] $msg" -ForegroundColor Green }

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($admin) {
    throw "Please don't use 'Run as administrator'. Close this and just double-click 'Install ANI.KOR.bat'."
}

# --- 1. Scoop (a no-admin app installer) -----------------------------------------------
$env:Path = "$env:USERPROFILE\scoop\shims;$env:USERPROFILE\.local\bin;$env:Path"
if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) {
    Say 'Installing Scoop (installs the other tools, no admin needed)...'
    Invoke-RestMethod -Uri 'https://get.scoop.sh' | Invoke-Expression
    $env:Path = "$env:USERPROFILE\scoop\shims;$env:Path"
}
Ok 'Scoop'

function Need($app, $cmd) {
    if ($cmd -and (Get-Command $cmd -ErrorAction SilentlyContinue)) { Ok $app; return }
    Say "Installing $app..."
    $ErrorActionPreference = 'Continue'   # scoop prints warnings that aren't failures
    scoop install $app | Out-Host
    $ErrorActionPreference = 'Stop'
    if ($cmd -and -not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "Could not install $app" }
    Ok $app
}

Need 'git' 'git'
$ErrorActionPreference = 'Continue'
$buckets = @(scoop bucket list | ForEach-Object { $_.Name })
if ($buckets -notcontains 'extras')     { scoop bucket add extras | Out-Host }
if ($buckets -notcontains 'nerd-fonts') { scoop bucket add nerd-fonts | Out-Host }
$ErrorActionPreference = 'Stop'
Need 'uv' 'uv'
Need 'fzf' 'fzf'
Need 'extras/mpv' 'mpv'
$ErrorActionPreference = 'Continue'
if (-not (scoop list 6>$null | Where-Object { $_.Name -eq 'CascadiaCode-NF-Mono' })) {
    Say 'Installing the ANI.KOR font (CaskaydiaCove Nerd Font)...'
    scoop install nerd-fonts/CascadiaCode-NF-Mono | Out-Host
}
$ErrorActionPreference = 'Stop'
Ok 'Font'
if (-not (Get-Command wt -ErrorAction SilentlyContinue)) {
    Need 'extras/windows-terminal' 'wt'
} else { Ok 'Windows Terminal' }

# --- 2. ANI.KOR itself -------------------------------------------------------------------
Say 'Finding the newest ANI.KOR...'
$rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ 'User-Agent' = 'anikor-installer' }
$whl = ($rel.assets | Where-Object { $_.name -like '*.whl' } | Select-Object -First 1).browser_download_url
if (-not $whl) { throw "The newest release ($($rel.tag_name)) has no package file yet. Try again in a few minutes." }
Say "Installing ANI.KOR $($rel.tag_name) (downloads Python the first time)..."
$ErrorActionPreference = 'Continue'   # uv shows progress on stderr
uv tool install --force --python 3.12 $whl | Out-Host
$code = $LASTEXITCODE
uv tool update-shell 2>$null | Out-Null
$ErrorActionPreference = 'Stop'
if ($code -ne 0) { throw 'Installing ANI.KOR failed' }
Ok "ANI.KOR $($rel.tag_name)"

# --- 3. Windows Terminal profile, launcher, shortcuts (done by ANI.KOR itself) -----------
$ErrorActionPreference = 'Continue'
anikor setup-windows
$ErrorActionPreference = 'Stop'
if ($LASTEXITCODE -ne 0) { throw 'Setting up the shortcut failed' }

Write-Host ''
Write-Host '  ANI.KOR is installed!' -ForegroundColor Magenta
Write-Host '  Double-click "ANI.KOR" on your desktop. The first time, it walks you through'
Write-Host '  linking your MyAnimeList (about 2 minutes).'
Write-Host ''

# ANI.KOR launcher for Windows (the desktop shortcut runs this inside Windows Terminal).
# Opens ANI.KOR. It never updates by itself: when a new version is out, ANI.KOR shows an
# UPDATE button; clicking it quits back to here with a flag file -> update -> reopen.
# Written by `anikor setup-windows`; refreshed automatically after each update.
param([switch]$Update, [int]$WaitPid = 0)

$ProgressPreference = 'SilentlyContinue'
$Repo = 'anikor-dev/anikor'
$Home_ = Join-Path $env:LOCALAPPDATA 'ANI.KOR'
$Flag = Join-Path $Home_ 'update-requested'
$env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\scoop\shims;$env:Path"
$env:ANIKOR_LAUNCHER = '1'
try { $Host.UI.RawUI.WindowTitle = 'ANI.KOR' } catch {}

if ($WaitPid) { try { Wait-Process -Id $WaitPid -Timeout 30 -ErrorAction SilentlyContinue } catch {} }

function Update-Anikor([switch]$Loud) {
    try {
        $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" `
            -Headers @{ 'User-Agent' = 'anikor-launcher' } -TimeoutSec 6
    } catch {
        if ($Loud) { Write-Host '  Could not reach GitHub to update. Opening the current version.' -ForegroundColor Yellow; Start-Sleep 2 }
        return
    }
    $want = $rel.tag_name.TrimStart('v')
    $have = ((anikor version) -replace '^ANI\.KOR\s*', '').Trim()
    try { $newer = [version]$want -gt [version]$have } catch { $newer = $want -ne $have }
    if (-not $newer) { return }
    $whl = ($rel.assets | Where-Object { $_.name -like '*.whl' } | Select-Object -First 1).browser_download_url
    if (-not $whl) { return }
    Write-Host ''
    Write-Host "  Updating ANI.KOR  v$have  ->  v$want ..." -ForegroundColor Magenta
    uv tool install --force --python 3.12 $whl | Out-Null
    if ($LASTEXITCODE -eq 0) {
        anikor setup-windows --quiet | Out-Null
        Write-Host '  Updated!' -ForegroundColor Green
    } else {
        Write-Host '  Update failed - opening the version you have.' -ForegroundColor Yellow
    }
    Start-Sleep 1
}

if ($Update) { Update-Anikor -Loud }
while ($true) {
    if (Test-Path $Flag) { Remove-Item $Flag -Force }
    anikor
    if (-not (Test-Path $Flag)) { break }
    Update-Anikor -Loud
}

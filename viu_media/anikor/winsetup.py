"""`anikor setup-windows`: Windows Terminal profile + launcher + desktop/Start shortcuts.

Run by the installer and again after every update (so fixes to these reach everyone).
Only writes inside %LOCALAPPDATA% and the user's Desktop / Start Menu.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent / "windows"
FONT = "CaskaydiaCove Nerd Font Mono"
PROFILE_GUID = "{6f1c3a52-9b7e-4d0a-8a5e-a71c0e2d4b19}"

# ANSI palette: the dashboard and menus use slots 13 (lavender), 9 (pink), 8 (dim)
SCHEME = {
    "name": "ANI.KOR",
    "background": "#15121F", "foreground": "#E6E1F5",
    "cursorColor": "#C9A7FF", "selectionBackground": "#3B3054",
    "black": "#1E1A2B", "red": "#E05A7A", "green": "#7FD1AE", "yellow": "#F2C879",
    "blue": "#7AA2F7", "purple": "#B48CF2", "cyan": "#78D0E0", "white": "#C8C2DA",
    "brightBlack": "#6E6787", "brightRed": "#FF6F9C", "brightGreen": "#9BE7C4",
    "brightYellow": "#FFDB94", "brightBlue": "#9DBBFF", "brightPurple": "#CDB0FF",
    "brightCyan": "#9EE6F2", "brightWhite": "#FFFFFF",
}


def _home() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "ANI.KOR"


def _ps(script: str) -> None:
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                   check=False, capture_output=True)


def _shortcut(lnk: Path, target: str, args: str, icon: Path) -> None:
    q = lambda s: str(s).replace("'", "''")
    _ps(f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{q(lnk)}');"
        f"$s.TargetPath='{q(target)}';$s.Arguments='{q(args)}';"
        f"$s.IconLocation='{q(icon)},0';$s.Description='ANI.KOR';"
        f"$s.WorkingDirectory='{q(Path.home())}';$s.Save()")


def setup(quiet: bool = False) -> int:
    if sys.platform != "win32":
        print("setup-windows only does something on Windows.")
        return 0
    say = (lambda *_: None) if quiet else (lambda m: print(f"  [ok] {m}"))
    home = _home()
    home.mkdir(parents=True, exist_ok=True)
    launcher = home / "anikor-launch.ps1"
    shutil.copyfile(HERE / "anikor-launch.ps1", launcher)
    icon = home / "anikor.ico"
    shutil.copyfile(HERE / "anikor.ico", icon)
    say("launcher")

    cmdline = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{launcher}"'
    frag_dir = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows Terminal" / "Fragments" / "ANI.KOR"
    frag_dir.mkdir(parents=True, exist_ok=True)
    (frag_dir / "anikor.json").write_text(json.dumps({
        "profiles": [{
            "guid": PROFILE_GUID, "name": "ANI.KOR", "commandline": cmdline,
            "icon": str(icon), "colorScheme": "ANI.KOR",
            "font": {"face": FONT, "size": 11},
            "opacity": 92, "useAcrylic": True, "padding": "8",
            "startingDirectory": "%USERPROFILE%", "closeOnExit": "always",
            "tabTitle": "ANI.KOR", "suppressApplicationTitle": True,
        }],
        "schemes": [SCHEME],
    }, indent=2), encoding="utf-8")
    say("Windows Terminal profile")

    wt = shutil.which("wt") or str(Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WindowsApps" / "wt.exe")
    if Path(wt).exists():
        target, args = wt, '-p "ANI.KOR"'
    else:   # no Windows Terminal: plain PowerShell window (icons may show as boxes)
        target, args = "powershell.exe", f'-NoProfile -ExecutionPolicy Bypass -File "{launcher}"'
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                       capture_output=True, text=True)
    desktop = Path(r.stdout.strip() or Path.home() / "Desktop")
    start = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    for d in (desktop, start):
        if d.exists():
            _shortcut(d / "ANI.KOR.lnk", target, args, icon)
    say("desktop + Start menu shortcut")
    return 0

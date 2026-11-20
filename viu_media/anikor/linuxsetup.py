"""`anikor setup-linux`: ANI.KOR's own kitty window + launcher + app-menu entry.

Run by linux/install.sh and again after every update (so fixes to these reach everyone).
Only writes inside ~/.local/share (XDG_DATA_HOME). The user's own kitty.conf is never
read or changed: the launcher starts kitty with `--config` pointing at ANI.KOR's file.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _data() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def home() -> Path:
    return _data() / "anikor"


def _kitty() -> str:
    """Prefer kitty from the official installer (~/.local/kitty.app) when the install put it there."""
    own = Path.home() / ".local" / "kitty.app" / "bin" / "kitty"
    return str(own) if own.exists() else (shutil.which("kitty") or "kitty")


def setup(quiet: bool = False) -> int:
    if sys.platform != "linux":
        print("setup-linux only does something on Linux.")
        return 0
    say = (lambda *_: None) if quiet else (lambda m: print(f"  [ok] {m}"))
    h = home()
    h.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(HERE / "linux" / "kitty.conf", h / "kitty.conf")
    launcher = h / "anikor-launch.sh"
    shutil.copyfile(HERE / "linux" / "anikor-launch.sh", launcher)
    launcher.chmod(0o755)
    say("kitty look + launcher")

    icon = h / "anikor.png"
    try:
        from PIL import Image
        with Image.open(HERE / "windows" / "anikor.ico") as im:
            im.size = max(im.info.get("sizes") or [im.size])
            im.convert("RGBA").save(icon)
    except Exception:  # noqa: BLE001
        icon = None

    kitty = _kitty()
    run = f'{kitty} --class anikor --title ANI.KOR --config "{h / "kitty.conf"}" "{launcher}"'
    # a tiny `anikor-kitty` command so it can be bound to a key or run from a terminal
    bindir = Path.home() / ".local" / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    cmd = bindir / "anikor-kitty"
    cmd.write_text(f"#!/bin/sh\n# opens ANI.KOR in its own kitty window (written by anikor setup-linux)\n"
                   f"exec {run} \"$@\"\n")
    cmd.chmod(0o755)

    apps = _data() / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    (apps / "anikor.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=ANI.KOR\n"
        "Comment=Anime dashboard synced with MyAnimeList\n"
        f"Exec={cmd}\n" + (f"Icon={icon}\n" if icon else "") +
        "Terminal=false\nCategories=AudioVideo;Video;Player;\nStartupWMClass=anikor\n"
        "Keywords=anime;myanimelist;mal;\n")
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(apps)], check=False, capture_output=True)
    say("app menu entry (search \"ANI.KOR\")")

    desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        d = desktop / "anikor.desktop"
        shutil.copyfile(apps / "anikor.desktop", d)
        d.chmod(0o755)
        if shutil.which("gio"):   # GNOME: mark it trusted so it opens on double-click
            subprocess.run(["gio", "set", str(d), "metadata::trusted", "true"],
                           check=False, capture_output=True)
        say("desktop shortcut")
    return 0

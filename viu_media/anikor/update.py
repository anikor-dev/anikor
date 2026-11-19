"""ANI.KOR updates: GitHub Releases of anikor-dev/anikor.

check()  -> {"current", "latest", "wheel", "notes"} when a newer release exists, else None.
            Cached for an hour; never raises, never takes longer than a few seconds.
start()  -> hand the update to a separate process and return; the caller exits ANI.KOR
            (Windows can't replace anikor.exe while it is running).

A source checkout installed in editable/dev mode never auto-updates (that's the
developer's own copy: `git pull` there instead).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

from . import paths

REPO = "anikor-dev/anikor"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
CACHE_FILE = paths.CACHE / "update.json"


def current() -> str:
    try:
        from importlib.metadata import version
        return version("anikor")
    except Exception:  # noqa: BLE001
        return "0"


def is_dev_install() -> bool:
    """Editable install (pip/uv -e) = someone's working copy: don't touch it."""
    try:
        from importlib.metadata import distribution
        raw = distribution("anikor").read_text("direct_url.json") or "{}"
        return bool(json.loads(raw).get("dir_info", {}).get("editable"))
    except Exception:  # noqa: BLE001
        return False


def _ver(v: str) -> tuple:
    out = []
    for part in v.lstrip("vV").split("."):
        num = "".join(c for c in part if c.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out)


def latest(max_age: float = 3600) -> dict | None:
    try:
        if time.time() - CACHE_FILE.stat().st_mtime < max_age:
            return json.loads(CACHE_FILE.read_text())
    except Exception:  # noqa: BLE001
        pass
    try:
        import httpx
        r = httpx.get(API, timeout=4, headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        rel = r.json()
        wheel = next((a["browser_download_url"] for a in rel.get("assets", [])
                      if a.get("name", "").endswith(".whl")), None)
        info = {"latest": rel.get("tag_name", "").lstrip("v"), "wheel": wheel,
                "notes": (rel.get("body") or "")[:2000]}
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(info))
        return info
    except Exception:  # noqa: BLE001
        return None


def check(max_age: float = 3600) -> dict | None:
    if os.environ.get("ANIKOR_NO_UPDATE") == "1" or is_dev_install():
        return None
    info = latest(max_age)
    if not info or not info.get("latest") or not info.get("wheel"):
        return None
    if _ver(info["latest"]) <= _ver(current()):
        return None
    return {**info, "current": current()}


def _launcher_ps1() -> str | None:
    """The Windows launcher the installer put next to the user's data (does update + start)."""
    base = os.environ.get("LOCALAPPDATA")
    p = os.path.join(base, "ANI.KOR", "anikor-launch.ps1") if base else None
    return p if p and os.path.exists(p) else None


def start(info: dict | None = None) -> str:
    """Begin updating in a separate process. Returns a message for the user."""
    info = info or check(max_age=0)
    if not info:
        return "ANI.KOR is already up to date."
    if sys.platform == "win32":
        ps1 = _launcher_ps1()
        if ps1 and os.environ.get("ANIKOR_LAUNCHER") == "1":
            # started from the desktop shortcut: the launcher updates + reopens when we quit
            open(os.path.join(os.path.dirname(ps1), "update-requested"), "w").close()
            return f"Updating to v{info['latest']}…"
        if ps1:
            # new console window: waits for this one to close, installs, restarts ANI.KOR
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1,
                 "-Update", "-WaitPid", str(os.getpid())],
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10))
            return f"Updating to v{info['latest']} — ANI.KOR will reopen by itself."
    uv = shutil.which("uv")
    if uv:
        subprocess.Popen([uv, "tool", "install", "--force", "--python", "3.12", info["wheel"]])
        return f"Updating to v{info['latest']} in the background — reopen ANI.KOR in a minute."
    return f"Update v{info['latest']} available: {info['wheel']}"

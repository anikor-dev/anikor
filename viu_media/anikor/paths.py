"""Where ANI.KOR keeps its own files.

Everything lives in the user's config/cache folders, never inside the install, so an
update (which replaces the install) keeps your login, cache and settings.
Linux: ~/.config/viu, ~/.cache/viu, ~/.cache/anikor   Windows: %LOCALAPPDATA%\\viu\\...
"""
import os
from pathlib import Path

from ..core.constants import APP_CACHE_DIR, APP_DATA_DIR, PLATFORM

if PLATFORM == "win32":
    CACHE = APP_CACHE_DIR / "anikor"
    CONFIG = APP_DATA_DIR / "anikor"
    BACK_FLAG = CACHE / "back-to-episodes"
else:
    CACHE = APP_CACHE_DIR.parent / "anikor"
    CONFIG = APP_DATA_DIR.parent / "anikor"
    BACK_FLAG = Path.home() / ".cache" / "anime-back"

MAL_TOKENS = APP_DATA_DIR / "mal.json"
MAL_ME = APP_CACHE_DIR / "mal-me.json"
RECENT = APP_CACHE_DIR / "anikor-recent.json"
LOG = Path(os.environ.get("ANIKOR_LOG") or CACHE / "anikor.log")

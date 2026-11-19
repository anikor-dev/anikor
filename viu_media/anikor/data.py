"""ANI.KOR home — data layer (MyAnimeList via viu_media.mal_sync).

Everything is cached on disk (paths.CACHE) so the dashboard opens instantly:
  * api/<key>.json  — MAL responses, fresh for 10 min, stale copies shown while a refresh runs
  * posters/<id>.jpg — small poster thumbnails (resized once, ~110px wide)
Layout code never talks to MAL directly; it asks for sections by name (SECTIONS below).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import io
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)
logging.getLogger("PIL").setLevel(logging.WARNING)   # PIL DEBUG chunk spam filled Viu's app.log

from .paths import CACHE, MAL_ME

API_DIR = CACHE / "api"
POSTER_DIR = CACHE / "posters"
TTL = 600  # seconds
FIELDS = ("fields=mean,num_list_users,media_type,num_episodes,my_list_status,"
          "main_picture,alternative_titles,status,start_season")
LIST_FIELDS = ("fields=list_status,num_episodes,main_picture,media_type,mean,"
               "alternative_titles,num_list_users,status")

_pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="anikor")
_lock = threading.Lock()
_mem: dict[str, tuple[float, object]] = {}     # key -> (fetched_at, data) — survives Viu round-trips


def season_now(today: _dt.date | None = None) -> tuple[int, str]:
    d = today or _dt.date.today()
    return d.year, ("winter", "winter", "winter", "spring", "spring", "spring",
                    "summer", "summer", "summer", "fall", "fall", "fall")[d.month - 1]


# ------------------------------------------------------------------ normalized entries
STATUS_BADGE = {"watching": "WATCH", "completed": "CMPL", "on_hold": "HOLD",
                "dropped": "DROP", "plan_to_watch": "PLAN"}
STATUS_NAME = {"watching": "Watching", "completed": "Completed", "on_hold": "On-Hold",
               "dropped": "Dropped", "plan_to_watch": "Plan to Watch"}
TYPE_NAME = {"tv": "TV", "ona": "ONA", "ova": "OVA", "movie": "Movie", "special": "Special",
             "tv_special": "TV Special", "music": "Music", "cm": "CM", "pv": "PV"}


def _entry(item: dict) -> dict:
    n = item.get("node", item)
    ls = item.get("list_status") or n.get("my_list_status") or {}
    alt = (n.get("alternative_titles") or {}).get("en") or ""
    pic = n.get("main_picture") or {}
    return {
        "id": n["id"],
        "title": n.get("title") or "?",
        "en": alt,
        "pic": pic.get("medium") or pic.get("large") or "",
        "mean": n.get("mean"),
        "members": n.get("num_list_users"),
        "type": TYPE_NAME.get(n.get("media_type") or "", (n.get("media_type") or "").upper()),
        "eps": n.get("num_episodes") or 0,
        "airing": n.get("status"),
        "rank": (item.get("ranking") or {}).get("rank"),
        "status": ls.get("status"),
        "watched": ls.get("num_episodes_watched", 0),
        "score": ls.get("score", 0),
        "updated": ls.get("updated_at"),
    }


def display_title(e: dict) -> str:
    """English title when MAL has one (shorter, easier to read), else the main title."""
    return e.get("en") or e.get("title") or "?"


def meta_line(e: dict) -> str:
    """'TV, 25 eps, scored 8.58' like MAL's ranking rows."""
    bits = [e["type"] or "?"]
    bits.append(f"{e['eps']} eps" if e.get("eps") else "? eps")
    bits.append(f"scored {e['mean']:.2f}" if e.get("mean") else "scored N/A")
    return ", ".join(bits)


def members(e: dict) -> str:
    m = e.get("members")
    return f"{m:,} members" if m else ""


# ------------------------------------------------------------------ cached API
def _mal(path: str):
    from .. import mal_sync
    return mal_sync._req("GET", path)


def _key(path: str) -> str:
    return hashlib.sha1(path.encode()).hexdigest()[:16]


def _disk_get(path: str):
    f = API_DIR / f"{_key(path)}.json"
    try:
        return f.stat().st_mtime, json.loads(f.read_text())
    except Exception:  # noqa: BLE001
        return None


def _disk_put(path: str, data) -> None:
    API_DIR.mkdir(parents=True, exist_ok=True)
    (API_DIR / f"{_key(path)}.json").write_text(json.dumps(data))


def cached(path: str):
    """(data, fresh) right now, without network. data None if never fetched."""
    with _lock:
        hit = _mem.get(path)
    if not hit:
        hit = _disk_get(path)
        if hit:
            with _lock:
                _mem[path] = hit
    if not hit:
        return None, False
    return hit[1], (time.time() - hit[0]) < TTL


_failed: dict[str, float] = {}
RETRY_AFTER = 60   # seconds: a failed fetch isn't retried by every redraw (that looped forever)


def recently_failed(path: str) -> bool:
    return time.time() - _failed.get(path, 0) < RETRY_AFTER


def fetch(path: str):
    """Network fetch + cache. Returns data, or the stale copy if MAL fails."""
    data = _mal(path)
    if data is None:
        _failed[path] = time.time()
        return cached(path)[0]
    _failed.pop(path, None)
    now = time.time()
    with _lock:
        _mem[path] = (now, data)
    try:
        _disk_put(path, data)
    except OSError:
        pass
    return data


def invalidate_lists() -> None:
    """After a list change: everything showing my_list_status is stale (kept for instant
    display, refetched on next view)."""
    import os
    with _lock:
        for k, (_, d) in list(_mem.items()):
            _mem[k] = (0.0, d)
    for f in API_DIR.glob("*.json"):
        try:
            os.utime(f, (0, 0))
        except OSError:
            pass
    try:
        os.remove(MAL_ME)
    except OSError:
        pass


# ------------------------------------------------------------------ sections
def _ranked(kind: str, limit: int) -> str:
    return f"/anime/ranking?ranking_type={kind}&limit={limit}&{FIELDS}"


def section_paths() -> dict[str, str]:
    y, s = season_now()
    return {
        "season": f"/anime/season/{y}/{s}?sort=anime_num_list_users&limit=30&{FIELDS}",
        "airing": _ranked("airing", 5),
        "upcoming": _ranked("upcoming", 5),
        "popular": _ranked("bypopularity", 5),
        "suggestions": f"/anime/suggestions?limit=24&{FIELDS}",
        "recent": f"/users/@me/animelist?sort=list_updated_at&limit=12&{LIST_FIELDS}",
        "me": "/users/@me?fields=anime_statistics",
    }


LIST_STATUSES = ["watching", "plan_to_watch", "completed", "on_hold", "dropped"]


def list_path(status: str) -> str:
    return f"/users/@me/animelist?status={status}&sort=list_updated_at&limit=200&{LIST_FIELDS}"


def search_path(q: str) -> str:
    from urllib.parse import quote
    return f"/anime?q={quote(q[:64])}&limit=24&{FIELDS}"


def entries(data) -> list[dict]:
    out = []
    for it in (data or {}).get("data", []):
        try:
            out.append(_entry(it))
        except Exception:  # noqa: BLE001
            continue
    return out


def profile(data) -> dict | None:
    if not data:
        return None
    st = data.get("anime_statistics") or {}
    return {
        "name": data.get("name", "?"),
        "days": st.get("num_days", 0), "mean": st.get("mean_score", 0),
        "episodes": st.get("num_episodes", 0), "total": st.get("num_items", 0),
        "watching": st.get("num_items_watching", 0), "completed": st.get("num_items_completed", 0),
        "on_hold": st.get("num_items_on_hold", 0), "dropped": st.get("num_items_dropped", 0),
        "plan_to_watch": st.get("num_items_plan_to_watch", 0),
        "rewatched": st.get("num_times_rewatched", 0),
    }


def submit(fn, *a):
    return _pool.submit(fn, *a)


# ------------------------------------------------------------------ posters
POSTER_W = 110


def poster_file(e: dict) -> Path:
    return POSTER_DIR / f"{e['id']}.png"


def poster(e: dict) -> Path | None:
    """Local thumbnail path (downloads + shrinks once). None if unavailable."""
    f = poster_file(e)
    if f.exists() and f.stat().st_size > 0:
        return f
    if not e.get("pic"):
        return None
    try:
        r = httpx.get(e["pic"], timeout=15, follow_redirects=True)
        r.raise_for_status()
        from PIL import Image
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        h = int(im.height * POSTER_W / im.width)
        im = im.resize((POSTER_W, h), Image.LANCZOS)
        POSTER_DIR.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        im.save(tmp, "PNG")
        tmp.replace(f)
        return f
    except Exception as ex:  # noqa: BLE001
        logger.debug("poster %s failed: %s", e.get("id"), ex)
        return None


# ------------------------------------------------------------------ list actions
def add_to_plan(mal_id: int) -> bool:
    from .. import mal_sync
    ok = mal_sync.push(mal_id, status="planning")
    if ok:
        invalidate_lists()
    return ok


def prefetch_all() -> None:
    """Warm every home section in the background (used at Viu start)."""
    for p in section_paths().values():
        if not cached(p)[1]:
            submit(fetch, p)


# ------------------------------------------------------------------ continue watching order
def _ts(iso: str | None) -> float:
    if not iso:
        return 0.0
    try:
        return _dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def continue_watching(watching: list[dict]) -> list[dict]:
    """MAL Watching list + anything started lately (rewatches of completed shows too),
    newest first: local start stamp (~/.cache/viu/anikor-recent.json, written by
    mal_sync.play_started) wins, MAL list_status.updated_at is the fallback."""
    from .. import mal_sync
    rec = mal_sync.recent()
    by_id = {e["id"]: e for e in watching}
    out = list(watching)
    for k, r in rec.items():
        mid = int(k)
        if mid in by_id:
            continue
        if time.time() - r.get("ts", 0) > 30 * 86400:   # stale extras drop off after a month
            continue
        e = {"id": mid, "title": r.get("title") or "?", "en": r.get("en") or "",
             "pic": r.get("pic") or "", "mean": None, "members": None, "type": "",
             "eps": r.get("eps") or 0, "airing": None, "rank": None, "status": None,
             "watched": 0, "score": 0, "updated": None}
        try:
            e["watched"] = max(0, int(float(r.get("ep") or 1)) - 1)
        except ValueError:
            pass
        out.append(e)

    def key(e):
        r = rec.get(str(e["id"]))
        return max(r["ts"] if r else 0.0, _ts(e.get("updated")))
    return sorted(out, key=key, reverse=True)

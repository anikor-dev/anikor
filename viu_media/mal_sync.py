"""MyAnimeList sync for Viu (local patch, 2026-11-18).

Viu was built for AniList only. This adds MyAnimeList as the tracker:
  * login:   python -m viu_media.mal_sync login <client_id>   (OAuth2 PKCE, local callback)
  * lists:   Viu's Watching/Planned/... menu entries read your MAL lists when you aren't
             logged into AniList (MAL ids -> AniList ids via AniList's idMal_in)
  * push:    a finished episode updates MAL (episodes watched + status)
  * resume:  the next episode comes from MAL progress

Tokens: mal.json in Viu's config folder (0600 on Linux). Everything here fails soft: a MAL error is
logged and Viu keeps playing.
"""
import http.server
import json
import logging
import os
import secrets
import sys
import time
import urllib.parse

import httpx

logger = logging.getLogger(__name__)
from .anikor import paths as _paths

TOKEN_FILE = _paths.MAL_TOKENS
API = "https://api.myanimelist.net/v2"
AUTH = "https://myanimelist.net/v1/oauth2"
REDIRECT = "http://localhost:8765/callback"
ANILIST = "https://graphql.anilist.co"

# Viu UserMediaListStatus.value -> MAL status
TO_MAL = {"watching": "watching", "current": "watching", "planning": "plan_to_watch",
          "completed": "completed", "paused": "on_hold", "dropped": "dropped",
          "repeating": "watching"}


def _load():
    try:
        return json.loads(TOKEN_FILE.read_text())
    except Exception:
        return None


def _save(d):
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(d, indent=1))
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass


def logged_in() -> bool:
    d = _load()
    return bool(d and d.get("refresh_token"))


def _token():
    d = _load()
    if not d:
        return None
    if time.time() > d.get("expires_at", 0) - 300:
        r = httpx.post(f"{AUTH}/token", data={
            "client_id": d["client_id"], "grant_type": "refresh_token",
            "refresh_token": d["refresh_token"]}, timeout=20)
        if r.status_code != 200:
            logger.error("MAL token refresh failed: %s %s", r.status_code, r.text[:200])
            return None
        t = r.json()
        d.update(access_token=t["access_token"], refresh_token=t["refresh_token"],
                 expires_at=time.time() + t["expires_in"])
        _save(d)
    return d["access_token"]


def _req(method, path, **kw):
    tok = _token()
    if not tok:
        return None
    try:
        r = httpx.request(method, f"{API}{path}", headers={"Authorization": f"Bearer {tok}"},
                          timeout=20, **kw)
        if r.status_code >= 400:
            logger.error("MAL %s %s -> %s %s", method, path, r.status_code, r.text[:200])
            return None
        return r.json()
    except Exception as e:  # noqa: BLE001
        logger.error("MAL %s %s failed: %s", method, path, e)
        return None


# ---------------------------------------------------------------- list / progress
_list_cache: dict = {}


def user_list(status: str) -> list[dict]:
    """[{mal_id, watched, status}] for one MAL status ('watching', 'plan_to_watch', ...)."""
    out, url = [], f"/users/@me/animelist?status={status}&limit=1000&fields=list_status&nsfw=true"
    data = _req("GET", url)
    for e in (data or {}).get("data", []):
        ls = e.get("list_status") or {}
        out.append({"mal_id": e["node"]["id"], "watched": ls.get("num_episodes_watched", 0),
                    "status": ls.get("status")})
        _list_cache[e["node"]["id"]] = out[-1]
    return out


def progress(mal_id) -> int | None:
    """Episodes watched on MAL for this show, None if unknown/not on list."""
    if not mal_id:
        return None
    if mal_id in _list_cache:
        return _list_cache[mal_id]["watched"]
    d = _req("GET", f"/anime/{mal_id}?fields=my_list_status")
    ls = (d or {}).get("my_list_status")
    if not ls:
        return None
    _list_cache[mal_id] = {"mal_id": mal_id, "watched": ls.get("num_episodes_watched", 0),
                           "status": ls.get("status")}
    return _list_cache[mal_id]["watched"]


def push(mal_id, episode=None, total=None, status=None, score=None) -> bool:
    """Update MAL. Episode count only ever moves forward (rewatching an old ep never
    lowers it); the last episode marks the show completed."""
    if not mal_id or not logged_in():
        return False
    body = {}
    if episode is not None:
        try:
            ep = int(float(episode))
        except (TypeError, ValueError):
            ep = None
        if ep is not None:
            cur = progress(mal_id) or 0
            if ep > cur:   # only forward progress touches MAL (a rewatch changes nothing)
                body["num_watched_episodes"] = ep
                if total and ep >= int(total):
                    body["status"] = "completed"
                elif not status:
                    body["status"] = "watching"
    if status:
        s = TO_MAL.get(str(getattr(status, "value", status)).lower())
        if s:
            body["status"] = s
            if s == "watching" and str(getattr(status, "value", status)).lower() == "repeating":
                body["is_rewatching"] = "true"
    if score:
        body["score"] = int(round(float(score) / 10 if float(score) > 10 else float(score)))
    if not body:
        return True
    r = _req("PATCH", f"/anime/{mal_id}/my_list_status", data=body)
    if r is not None:
        _list_cache[mal_id] = {"mal_id": mal_id, "watched": r.get("num_episodes_watched", 0),
                               "status": r.get("status")}
        logger.info("MAL updated %s: %s", mal_id, body)
    return r is not None


def anilist_ids(mal_ids: list[int]) -> list[int]:
    """MAL ids -> AniList ids (same order), via AniList's public idMal_in."""
    q = ("query($ids:[Int],$p:Int){Page(page:$p,perPage:50){pageInfo{hasNextPage}"
         "media(idMal_in:$ids,type:ANIME){id idMal}}}")
    found = {}
    for i in range(0, len(mal_ids), 50):
        chunk = mal_ids[i:i + 50]
        try:
            r = httpx.post(ANILIST, json={"query": q, "variables": {"ids": chunk, "p": 1}},
                           timeout=20)
            for m in r.json()["data"]["Page"]["media"]:
                found[m["idMal"]] = m["id"]
        except Exception as e:  # noqa: BLE001
            logger.error("AniList id lookup failed: %s", e)
    return [found[m] for m in mal_ids if m in found]


# ---------------------------------------------------------------- login
def login(client_id: str):
    verifier = secrets.token_urlsafe(64)[:100]   # MAL only supports PKCE "plain"
    state = secrets.token_urlsafe(16)
    url = f"{AUTH}/authorize?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": client_id, "code_challenge": verifier,
        "code_challenge_method": "plain", "state": state, "redirect_uri": REDIRECT})
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Viu is linked to MyAnimeList. You can close this tab.</h2>")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 8765), H)
    print("Opening MyAnimeList in your browser... click Allow.")
    print(f"(If it doesn't open, visit:)\n{url}\n")
    import webbrowser
    webbrowser.open(url)
    srv.timeout = 300
    while "code" not in got and "error" not in got:
        srv.handle_request()
    if got.get("error") or got.get("state") != state:
        sys.exit(f"MAL login failed: {got.get('error') or 'state mismatch'}")
    r = httpx.post(f"{AUTH}/token", data={
        "client_id": client_id, "grant_type": "authorization_code", "code": got["code"],
        "code_verifier": verifier, "redirect_uri": REDIRECT}, timeout=20)
    if r.status_code != 200:
        sys.exit(f"MAL token exchange failed: {r.status_code} {r.text[:300]}")
    t = r.json()
    _save({"client_id": client_id, "access_token": t["access_token"],
           "refresh_token": t["refresh_token"], "expires_at": time.time() + t["expires_in"]})
    me = _req("GET", "/users/@me") or {}
    print(f"✅ Linked to MyAnimeList as {me.get('name', '?')}. "
          f"Watching: {len(user_list('watching'))} shows.")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "login":
        login(sys.argv[2].strip())
    elif len(sys.argv) >= 2 and sys.argv[1] == "status":
        print("logged in" if logged_in() and _req("GET", "/users/@me") else "not logged in")
    else:
        print("usage: anikor login [client_id] | anikor login status")


# ---------------------------------------------------------------- profile (menu header) 2026-11-18
def me() -> dict | None:
    """MAL name + list counts for the Viu menu header. Cached 10 min so the menu stays instant."""
    import json, os, time
    path = str(_paths.MAL_ME)
    try:
        if time.time() - os.path.getmtime(path) < 600:
            return json.load(open(path))
    except Exception:  # noqa: BLE001
        pass
    if not logged_in():
        return None
    d = _req("GET", "/users/@me?fields=anime_statistics")
    if not d:
        try:
            return json.load(open(path))   # offline: last known
        except Exception:  # noqa: BLE001
            return None
    st = d.get("anime_statistics") or {}
    out = {"name": d.get("name"), "watching": st.get("num_items_watching", 0),
           "planned": st.get("num_items_plan_to_watch", 0), "completed": st.get("num_items_completed", 0),
           "paused": st.get("num_items_on_hold", 0), "dropped": st.get("num_items_dropped", 0),
           "days": st.get("num_days", 0), "episodes": st.get("num_episodes", 0), "mean": st.get("mean_score", 0)}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, "w"))
    return out


_push_original = push


def push(*a, **k):  # noqa: F811 — after any list change, the header counts refresh next menu
    ok = _push_original(*a, **k)
    if ok:
        import os
        try:
            os.remove(str(_paths.MAL_ME))
        except OSError:
            pass
    return ok


# ---------------------------------------------------------------- playback hooks (ANI.KOR 2026-11-18)
# Start of an episode -> local "last watched" stamp (Continue Watching order) + MAL status
# watching (completed shows get is_rewatching instead). End of an episode -> progress via
# push() (forward-only; last episode = completed). All MAL calls run on a background thread
# so playback never waits; failures go to the ANI.KOR log (anikor.log in the cache folder).
# ANIKOR_MAL_DRYRUN=1 logs the PATCH bodies instead of sending them (testing).
RECENT_FILE = _paths.RECENT
CTL_LOG = _paths.LOG


def _ctl_log(msg: str) -> None:
    try:
        with open(CTL_LOG, "a") as f:
            f.write(f"{time.strftime('%T')} mal-sync {msg}\n")
    except OSError:
        pass


def _bg(name, fn, *a, **k):
    import threading

    def run():
        try:
            ok = fn(*a, **k)
            _ctl_log(f"{'FAILED' if ok is False else 'ok'} {name} {a} {k}")
        except Exception as e:  # noqa: BLE001
            _ctl_log(f"FAILED {name} {a}: {e}")
    # non-daemon: a push started right before Viu quits still finishes
    t = threading.Thread(target=run, name=f"mal-{name}", daemon=False)
    t.start()
    return t


def recent() -> dict:
    """{str(mal_id): {ts, ep, title, en, pic, eps}} — newest stamp = last started."""
    try:
        return json.loads(RECENT_FILE.read_text())
    except Exception:  # noqa: BLE001
        return {}


def mark_recent(media_item, episode) -> None:
    mal_id = getattr(media_item, "id_mal", None)
    if not mal_id:
        return
    d = recent()
    t = media_item.title
    cov = getattr(media_item, "cover_image", None)
    d[str(mal_id)] = {"ts": time.time(), "ep": str(episode), "anilist": media_item.id,
                      "title": t.romaji or t.english, "en": t.english or "",
                      "pic": (cov.large or cov.medium) if cov else "",
                      "eps": media_item.episodes or 0}
    d = dict(sorted(d.items(), key=lambda kv: -kv[1]["ts"])[:60])
    try:
        RECENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = RECENT_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d))
        tmp.replace(RECENT_FILE)
    except OSError as e:
        _ctl_log(f"recent write failed: {e}")


def _patch(mal_id, body) -> bool:
    if os.environ.get("ANIKOR_MAL_DRYRUN") == "1":
        _ctl_log(f"DRYRUN PATCH {mal_id} {body}")
        return True
    r = _req("PATCH", f"/anime/{mal_id}/my_list_status", data=body)
    if r is not None:
        _list_cache[mal_id] = {"mal_id": mal_id, "watched": r.get("num_episodes_watched", 0),
                               "status": r.get("status")}
        try:
            os.remove(str(_paths.MAL_ME))
        except OSError:
            pass
        _ctl_log(f"MAL {mal_id} {body}")
    return r is not None


def _start_push(mal_id) -> bool:
    if not logged_in():
        return True
    d = _req("GET", f"/anime/{mal_id}?fields=my_list_status")
    if d is None:
        return False
    ls = d.get("my_list_status") or {}
    st = ls.get("status")
    if st == "watching":
        return True
    if st == "completed":
        if ls.get("is_rewatching"):
            return True
        return _patch(mal_id, {"is_rewatching": "true"})
    return _patch(mal_id, {"status": "watching"})


def play_started(media_item, episode) -> None:
    """Call right before the player opens. Never blocks."""
    try:
        mark_recent(media_item, episode)
    except Exception as e:  # noqa: BLE001
        _ctl_log(f"recent failed: {e}")
    mal_id = getattr(media_item, "id_mal", None)
    if mal_id:
        _bg("start", _start_push, mal_id)


def play_finished(media_item, episode) -> None:
    """Call after an episode counted as watched (Viu's episode_complete_at). Never blocks."""
    mal_id = getattr(media_item, "id_mal", None)
    if mal_id and logged_in():
        if os.environ.get("ANIKOR_MAL_DRYRUN") == "1":
            _ctl_log(f"DRYRUN finish {mal_id} episode={episode} total={media_item.episodes}")
            return
        _bg("finish", push, mal_id, episode=episode, total=media_item.episodes)


def set_list(media_item, status=None, score=None) -> bool:
    """Viu's Add/Update List / Bulk / Score actions -> MAL too (2026-11-18).
    status: UserMediaListStatus or its value. completed also sets episodes = total;
    repeating -> watching + is_rewatching (via push)."""
    mal_id = getattr(media_item, "id_mal", None)
    if not mal_id or not logged_in():
        return False
    s = str(getattr(status, "value", status) or "").lower() or None
    total = getattr(media_item, "episodes", None)
    ep = total if (s == "completed" and total) else None
    if os.environ.get("ANIKOR_MAL_DRYRUN") == "1":
        _ctl_log(f"DRYRUN set_list {mal_id} status={s} episode={ep} score={score}")
        return True
    _list_cache.pop(mal_id, None)
    ok = push(mal_id, episode=ep, total=total, status=s, score=score)
    _ctl_log(f"{'ok' if ok else 'FAILED'} set_list {mal_id} status={s} episode={ep} score={score}")
    if ok:
        try:
            from .anikor import data as _d
            _d.invalidate_lists()
        except Exception:  # noqa: BLE001
            pass
    return ok

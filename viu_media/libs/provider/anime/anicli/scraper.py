"""Independent Python re-implementation of the four HTTP steps ani-cli 5.1 uses for
hianime, so the anime source works on Windows without bash/curl.

    search(query)                 -> [(show_id, title), ...]
    episodes(show_id)             -> [(episode_id, episode_number), ...]
    streams(show_id, ep, "sub")   -> {"referer", "master", "subtitle", "links": [(quality, url)]}

When the site changes, this file is the one to fix (compare with ani-cli's
hianime_search / hianime_episodes / hianime_m3u8 functions).
"""
from __future__ import annotations

import base64
import html
import json
import re

import httpx

BASE = "https://hianime.at"
SEARCH = BASE + "/search"
EPISODES = BASE + "/api/theme/episode/list/{}"
SERVERS = BASE + "/api/theme/episode/servers"
AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
# the embed page ships its config as base64(json XOR this key)
EMBED_KEY = b"otaku-embed-v1"


class Blocked(RuntimeError):
    pass


def _get(url: str, referer: str | None = None, **params) -> str:
    headers = {"User-Agent": AGENT}
    if referer:
        headers["Referer"] = referer
    r = httpx.get(url, params=params or None, headers=headers, follow_redirects=True, timeout=15)
    if "Just a moment" in r.text[:2000] and "<title>" in r.text[:2000]:
        raise Blocked("the anime site is behind a Cloudflare check right now")
    r.raise_for_status()
    return r.text


def _b64(s: str) -> bytes:
    s = s.strip()
    return base64.b64decode(s + "=" * (-len(s) % 4))


def search(query: str) -> list[tuple[str, str]]:
    page = _get(SEARCH, keyword=query)
    # the top-10 sidebar repeats the result markup: cut it off first
    page = page.split('id="main-sidebar"', 1)[0].replace("\n", " ")
    out = []
    for chunk in page.split('<div class="film-detail">')[1:]:
        m = re.search(r'<h3 class="film-name">\s*<a href="[^"]*/([^"/]*)"\s*title="([^"]*)"', chunk)
        if m:
            out.append((m.group(1), html.unescape(m.group(2))))
    return out


def episodes(show_id: str) -> list[tuple[str, str]]:
    page = _get(EPISODES.format(show_id.rsplit("-", 1)[-1])).replace("\\", "")
    out, seen = [], set()
    pat = re.compile(r'data-number="([^"]*)".*data-id="([0-9]+)".*/watch/' + re.escape(show_id) + r"\?ep=")
    for chunk in page.split("ep-item")[1:]:
        m = pat.search(chunk)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            out.append((m.group(2), m.group(1)))
    return out


def _deobfuscate(blob: str) -> str:
    raw = _b64(blob)
    return bytes(b ^ EMBED_KEY[i % len(EMBED_KEY)] for i, b in enumerate(raw)).decode("utf-8", "replace")


def streams(show_id: str, episode: str, mode: str = "sub") -> dict | None:
    ep_id = next((eid for eid, num in episodes(show_id) if num == str(episode)), None)
    if not ep_id:
        return None
    servers = _get(SERVERS, episodeId=ep_id).replace('\\"', '"')
    embed_hash = None
    for chunk in servers.split("server-item")[1:]:
        m = re.search(r'data-type="' + re.escape(mode) + r'".*data-server-name="ZokoAnime".*data-hash="([^"]*)"', chunk)
        if m:
            embed_hash = m.group(1)
            break
    if not embed_hash:
        return None
    embed = _b64(embed_hash).decode("utf-8", "replace").strip()
    m = re.match(r"(https?://[^/]*)", embed)
    if not m:
        return None
    referer = m.group(1) + "/"
    m = re.search(r'window\.__P="([^"]*)"', _get(embed))
    if not m:
        return None
    cfg_text = _deobfuscate(m.group(1))
    master = subtitle = None
    try:
        cfg = json.loads(cfg_text)
    except ValueError:
        cfg = None
    if isinstance(cfg, dict):
        master = _find_m3u8(cfg)
        subs = cfg.get("subtitles") or []
        default = next((s for s in subs if isinstance(s, dict) and s.get("default")), None)
        subtitle = default.get("src") if default else None
    if not master:   # same fallbacks as the shell version
        found = re.findall(r'"src":"([^"]*\.m3u8[^"]*)"', cfg_text)
        master = found[-1] if found else None
    if not subtitle:
        sm = re.search(r'"subtitles":\[(.*?)\]', cfg_text)
        if sm:
            for part in sm.group(1).split("},{"):
                if '"default":true' in part:
                    s2 = re.search(r'"src":"([^"]*)"', part)
                    subtitle = s2.group(1) if s2 else None
                    break
    if not master:
        return None
    links = []
    lines = _get(master, referer=referer).splitlines()
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
            res = re.search(r"RESOLUTION=\d+x(\d+)", line)
            url = lines[i + 1].strip()
            if res and url and not url.startswith("#"):
                if not url.startswith("http"):
                    url = master.rsplit("/", 1)[0] + "/" + url
                links.append((res.group(1), url))
    links.sort(key=lambda x: -int(x[0]))
    return {"referer": referer, "master": master, "subtitle": subtitle, "links": links}


def _find_m3u8(obj):
    if isinstance(obj, dict):
        src = obj.get("src")
        if isinstance(src, str) and ".m3u8" in src:
            return src
        for v in obj.values():
            r = _find_m3u8(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_m3u8(v)
            if r:
                return r
    return None

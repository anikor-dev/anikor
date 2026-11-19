"""anicli source: Viu's menus, ani-cli's scraping (hianime).

The scraping runs in pure Python (scraper.py, a port of ani-cli's own functions), so it
works on Windows too. If that fails and an `ani-bridge` helper is on PATH (a Linux setup
that borrows a system ani-cli's live functions), it is tried as a fallback — so a fresh
ani-cli from the package manager can still fix a broken site there.
"""
import logging
import os
import re
import shutil
import subprocess
from functools import lru_cache
from typing import Iterator

from ..base import BaseAnimeProvider
from ..params import AnimeParams, EpisodeStreamsParams, SearchParams
from ..types import (Anime, AnimeEpisodes, EpisodeStream, MediaTranslationType,
                     PageInfo, SearchResult, SearchResults, Server, Subtitle)
from . import scraper

logger = logging.getLogger(__name__)
BRIDGE = os.environ.get("ANI_BRIDGE") or shutil.which("ani-bridge")


def _run(*args, timeout=60) -> str:
    """ani-bridge fallback (Linux only, optional)."""
    if not BRIDGE:
        return ""
    try:
        r = subprocess.run([BRIDGE, *args], capture_output=True, text=True, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        logger.error("ani-bridge %s failed: %s", args[0], e)
        return ""
    if r.returncode != 0:
        logger.error("ani-bridge %s failed: %s", args[0], r.stderr.strip()[-300:])
    return r.stdout


def _search_lines(query: str) -> list[tuple[str, str]]:
    try:
        res = scraper.search(query)
        if res:
            return res
    except Exception as e:  # noqa: BLE001
        logger.error("search failed: %s", e)
    return [tuple(l.split("\t", 1)) for l in _run("search", query).splitlines() if "\t" in l]


def _episode_numbers(show_id: str) -> list[str]:
    try:
        eps = [num for _, num in scraper.episodes(show_id)]
    except Exception as e:  # noqa: BLE001
        logger.error("episode list failed: %s", e)
        eps = []
    if not eps:
        eps = [e.strip() for e in _run("episodes", show_id).splitlines() if e.strip()]
    key = lambda e: (float(e) if re.fullmatch(r"\d+(\.\d+)?", e) else 1e9, e)
    return sorted(set(eps), key=key)


def _links_lines(show_id: str, episode: str, mode: str) -> list[str]:
    """Same line format the bridge prints: REFERER/MASTER/SUB/<quality> <url>."""
    try:
        st = scraper.streams(show_id, episode, mode)
    except Exception as e:  # noqa: BLE001
        logger.error("stream lookup failed: %s", e)
        st = None
    if st:
        out = [f"REFERER {st['referer']}", f"MASTER {st['master']}"]
        if st.get("subtitle"):
            out.append(f"SUB {st['subtitle']}")
        out += [f"{q} {u}" for q, u in st["links"]]
        return out
    return _run("links", show_id, episode, mode).splitlines()


class AniCli(BaseAnimeProvider):
    HEADERS = {}

    def search(self, params: SearchParams) -> SearchResults | None:
        return self._search(params.query)

    @lru_cache()
    def _search(self, query: str) -> SearchResults | None:
        res = []
        for sid, title in _search_lines(query):
            res.append(SearchResult(id=sid, title=title.strip(), episodes=AnimeEpisodes(sub=[])))
        if not res:
            return None
        return SearchResults(page_info=PageInfo(total=len(res), current_page=1), results=res)

    def get(self, params: AnimeParams) -> Anime | None:
        eps = _episode_numbers(params.id)
        if not eps:
            return None
        title = next((r.title for r in (self._search(params.query) or SearchResults(
            page_info=PageInfo(), results=[])).results if r.id == params.id), params.query)
        # the site doesn't say which episodes have a dub up front; asking for one tries it
        return Anime(id=params.id, title=title, episodes=AnimeEpisodes(sub=eps, dub=eps))

    def episode_streams(self, params: EpisodeStreamsParams) -> Iterator[Server] | None:
        out = _links_lines(params.anime_id, str(params.episode), params.translation_type)
        headers, subs, links, master = {}, [], [], None
        for line in out:
            key, _, val = line.partition(" ")
            if key == "MASTER" and val.startswith("http"):
                master = val.strip()
            elif key == "REFERER":
                headers["Referer"] = val.strip()
            # (AGENT is skipped: Viu joins mpv headers with commas and the UA has one,
            # which garbles the request into a 400; the referer alone is what the host checks)
            elif key == "SUB":
                subs.append(Subtitle(url=val.strip(), language="English"))
            elif key in ("1080", "720", "480", "360") and val.startswith("http"):
                links.append(EpisodeStream(
                    link=val.strip(), quality=key, hls=True,
                    translation_type=MediaTranslationType(params.translation_type)))
        if not links:
            return
        if master:
            # play the master playlist: it has the audio tracks (variant playlists can be
            # video-only = no sound). mpv picks the best quality from it by itself.
            links = [EpisodeStream(link=master, quality=l.quality, hls=True,
                                   translation_type=l.translation_type) for l in links]
        yield Server(name="TOP", links=links, episode_title=f"Episode {params.episode}",
                     headers=headers, subtitles=subs)

"""ANI.KOR home <-> Viu session glue.

Viu's MAIN menu calls home_menu() when ANIKOR_HOME=1 (set by the `anikor` command).
Picking a show builds the AniList MediaItem and returns a MEDIA_ACTIONS State, so Viu's own
Stream / Episodes / MAL sync all run unchanged. Backing out of Viu to MAIN
(Tab on media actions) lands here again.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_classic_once = False


def want_classic() -> bool:
    """True once after the user picked 'c' (classic text menu)."""
    global _classic_once
    if _classic_once:
        _classic_once = False
        return True
    return False


def media_state(ctx, entry: dict):
    """MAL entry -> Viu State(MEDIA_ACTIONS) for that show, or None."""
    from .. import mal_sync
    from ..cli.interactive.state import MediaApiState, MenuName, State
    from ..libs.media_api.params import MediaSearchParams

    item = None
    ids = mal_sync.anilist_ids([entry["id"]])
    if ids:
        res = ctx.media_api.search_media(MediaSearchParams(id_in=ids, per_page=1))
        if res and res.media:
            item = res.media[0]
    if item is None:   # not mapped on AniList yet: best title match
        for q in (entry.get("en"), entry.get("title")):
            if not q:
                continue
            res = ctx.media_api.search_media(MediaSearchParams(query=q, per_page=5))
            if res and res.media:
                item = next((m for m in res.media if getattr(m, "id_mal", None) == entry["id"]),
                            res.media[0])
                break
    if item is None:
        return None
    return State(menu_name=MenuName.MEDIA_ACTIONS,
                 media_api=MediaApiState(search_result={item.id: item}, media_id=item.id))


def home_menu(ctx, state):
    """The MAIN menu when ANI.KOR home is on. Returns a State or InternalDirective."""
    global _classic_once
    from ..cli.interactive.state import InternalDirective
    from .app import run_home

    ctx.feedback.clear_console()
    try:
        res = run_home()
    except Exception as e:  # noqa: BLE001 — never strand the user: fall back to the text menu
        logger.exception("ANI.KOR home crashed")
        ctx.feedback.error(f"ANI.KOR home failed ({e}); classic menu instead")
        _classic_once = True
        return InternalDirective.RELOAD
    if not res:
        return InternalDirective.EXIT
    kind = res[0]
    if kind == "exit":
        return InternalDirective.EXIT
    if kind == "update":
        from . import update
        msg = update.start(res[1])
        ctx.feedback.info(msg)
        return InternalDirective.EXIT
    if kind == "classic":
        _classic_once = True
        return InternalDirective.RELOAD
    if kind == "open":
        entry = res[1]
        title = entry.get("en") or entry.get("title")
        with ctx.feedback.progress(f"Opening {title}"):
            try:
                st = media_state(ctx, entry)
            except Exception as e:  # noqa: BLE001
                logger.exception("handoff failed")
                st = None
        if st is None:
            ctx.feedback.error(f"Couldn't find {title} on AniList")
            return InternalDirective.RELOAD
        return st
    return InternalDirective.RELOAD

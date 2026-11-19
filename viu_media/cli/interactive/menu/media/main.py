import logging
import random
from typing import Callable, Dict

from .....libs.media_api.params import MediaSearchParams, UserMediaListSearchParams
from .....libs.media_api.types import (
    MediaSort,
    MediaStatus,
    UserMediaListStatus,
)
from ...session import Context, session
from ...state import InternalDirective, MediaApiState, MenuName, State

logger = logging.getLogger(__name__)
MenuAction = Callable[[], State | InternalDirective]


@session.menu
def main(ctx: Context, state: State) -> State | InternalDirective:
    # ANI.KOR home: the poster dashboard replaces this text menu when
    # launched via `anikor` (ANIKOR_HOME=1). 'c' there opens this classic menu once.
    import os
    if os.environ.get("ANIKOR_HOME") == "1":
        from .....anikor import bridge
        if not bridge.want_classic():
            return bridge.home_menu(ctx, state)
    return _classic_main(ctx, state)


def _classic_main(ctx: Context, state: State) -> State | InternalDirective:
    icons = ctx.config.general.icons
    feedback = ctx.feedback
    feedback.clear_console()

    # ANI.KOR: MAL profile up top — name + counts — and your lists first.
    try:
        from ..... import mal_sync
        me = mal_sync.me()
    except Exception:  # noqa: BLE001
        me = None
    n = lambda k: f"  {me[k]}" if me and me.get(k) else ""
    L, P, W, D = "\033[38;5;13m", "\033[38;5;9m", "\033[38;5;15m", "\033[38;5;8m"
    R = "\033[0m"
    profile = None
    if me:
        profile = (f" {P}󰀄{R}  {W}\033[1m{me['name']}{R}  {D}·  MyAnimeList{R}\n"
                   f" {L}󰐊{R} {me['watching']} watching   {L}󰃀{R} {me['planned']} planned   "
                   f"{L}󰄬{R} {me['completed']} completed   {L}󰥔{R} {me['days']:.1f} days   "
                   f"{L}󰓎{R} {me['mean']}\n")

    options: Dict[str, MenuAction] = {
        f"{'📺 ' if icons else ''}Watching{n('watching')}": _create_user_list_action(
            ctx, state, UserMediaListStatus.WATCHING
        ),
        f"{'📑 ' if icons else ''}Planned{n('planned')}": _create_user_list_action(
            ctx, state, UserMediaListStatus.PLANNING
        ),
        f"{'⏸️ ' if icons else ''}Paused{n('paused')}": _create_user_list_action(
            ctx, state, UserMediaListStatus.PAUSED
        ),
        f"{'✅ ' if icons else ''}Completed{n('completed')}": _create_user_list_action(
            ctx, state, UserMediaListStatus.COMPLETED
        ),
        f"{'🚮 ' if icons else ''}Dropped{n('dropped')}": _create_user_list_action(
            ctx, state, UserMediaListStatus.DROPPED
        ),
        f"{'🔁 ' if icons else ''}Rewatching": _create_user_list_action(
            ctx, state, UserMediaListStatus.REPEATING
        ),
        f"{'🔎 ' if icons else ''}Search": _create_search_media_list(ctx, state),
        f"{'🔥 ' if icons else ''}Trending": _create_media_list_action(
            ctx, state, MediaSort.TRENDING_DESC
        ),
        f"{'🎞️ ' if icons else ''}Recent": _create_recent_media_action(ctx, state),
        f"{'✨ ' if icons else ''}Popular": _create_media_list_action(
            ctx, state, MediaSort.POPULARITY_DESC
        ),
        f"{'💯 ' if icons else ''}Top Scored": _create_media_list_action(
            ctx, state, MediaSort.SCORE_DESC
        ),
        f"{'🔔 ' if icons else ''}Recently Updated": _create_media_list_action(
            ctx, state, MediaSort.UPDATED_AT_DESC
        ),
        f"{'🎬 ' if icons else ''}Upcoming": _create_media_list_action(
            ctx, state, MediaSort.POPULARITY_DESC, MediaStatus.NOT_YET_RELEASED
        ),
        f"{'💖 ' if icons else ''}Favourites": _create_media_list_action(
            ctx, state, MediaSort.FAVOURITES_DESC
        ),
        f"{'🎲 ' if icons else ''}Random": _create_random_media_list(ctx, state),
        f"{'🔍 ' if icons else ''}Dynamic Search": _create_dynamic_search_action(
            ctx, state
        ),
        f"{'🏠 ' if icons else ''}Downloads": _create_downloads_action(ctx, state),
        f"{'📝 ' if icons else ''}Edit Config": lambda: InternalDirective.CONFIG_EDIT,
        f"{'❌ ' if icons else ''}Exit": lambda: InternalDirective.EXIT,
    }

    choice = ctx.selector.choose(
        prompt="Select Category",
        choices=list(options.keys()),
        header=profile,
    )
    if not choice:
        return InternalDirective.MAIN

    selected_action = options[choice]

    next_step = selected_action()
    return next_step


def _create_media_list_action(
    ctx: Context, state: State, sort: MediaSort, status: MediaStatus | None = None
) -> MenuAction:
    def action():
        feedback = ctx.feedback
        search_params = MediaSearchParams(sort=sort, status=status)

        loading_message = "Fetching media list"
        result = None
        with feedback.progress(loading_message):
            result = ctx.media_api.search_media(search_params)

        if result:
            return State(
                menu_name=MenuName.RESULTS,
                media_api=MediaApiState(
                    search_result={
                        media_item.id: media_item for media_item in result.media
                    },
                    search_params=search_params,
                    page_info=result.page_info,
                ),
            )
        else:
            return InternalDirective.MAIN

    return action


def _create_random_media_list(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.feedback
        search_params = MediaSearchParams(id_in=random.sample(range(1, 15000), k=50))

        loading_message = "Fetching media list"
        result = None
        with feedback.progress(loading_message):
            result = ctx.media_api.search_media(search_params)

        if result:
            return State(
                menu_name=MenuName.RESULTS,
                media_api=MediaApiState(
                    search_result={
                        media_item.id: media_item for media_item in result.media
                    },
                    search_params=search_params,
                    page_info=result.page_info,
                ),
            )
        else:
            return InternalDirective.MAIN

    return action


def _create_search_media_list(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.feedback

        query = ctx.selector.ask("Search for Anime")
        if not query:
            return InternalDirective.MAIN

        search_params = MediaSearchParams(query=query)

        loading_message = "Fetching media list"
        result = None
        with feedback.progress(loading_message):
            result = ctx.media_api.search_media(search_params)

        if result:
            return State(
                menu_name=MenuName.RESULTS,
                media_api=MediaApiState(
                    search_result={
                        media_item.id: media_item for media_item in result.media
                    },
                    search_params=search_params,
                    page_info=result.page_info,
                ),
            )
        else:
            return InternalDirective.MAIN

    return action


def _create_user_list_action(
    ctx: Context, state: State, status: UserMediaListStatus
) -> MenuAction:
    """A factory to create menu actions for fetching user lists, handling authentication."""

    def action():
        feedback = ctx.feedback
        if not ctx.media_api.is_authenticated():
            # ANI.KOR: MyAnimeList lists
            from ..... import mal_sync
            if not mal_sync.logged_in():
                feedback.error("You haven't logged in (run: anikor login)")
                return InternalDirective.MAIN
            mal_status = {"watching": "watching", "current": "watching",
                          "repeating": "watching", "paused": "on_hold",
                          "planning": "plan_to_watch", "completed": "completed",
                          "dropped": "dropped"}.get(status.value.lower(), "watching")
            with feedback.progress("Fetching your MyAnimeList"):
                entries = mal_sync.user_list(mal_status)
                if status.value.lower() == "repeating":
                    entries = []  # MAL has no separate rewatching list
                ids = mal_sync.anilist_ids([e["mal_id"] for e in entries])
            if not ids:
                feedback.info("Nothing on that MyAnimeList list")
                return InternalDirective.MAIN
            search_params = MediaSearchParams(id_in=ids, per_page=50)
            with feedback.progress("Fetching media list"):
                result = ctx.media_api.search_media(search_params)
            if not result:
                return InternalDirective.MAIN
            order = {i: n for n, i in enumerate(ids)}
            media = sorted(result.media, key=lambda m: order.get(m.id, 1e9))
            return State(
                menu_name=MenuName.RESULTS,
                media_api=MediaApiState(
                    search_result={m.id: m for m in media},
                    search_params=search_params,
                    page_info=result.page_info,
                ),
            )

        search_params = UserMediaListSearchParams(status=status)

        loading_message = "Fetching media list"
        result = None
        with feedback.progress(loading_message):
            result = ctx.media_api.search_media_list(search_params)

        if result:
            return State(
                menu_name=MenuName.RESULTS,
                media_api=MediaApiState(
                    search_result={
                        media_item.id: media_item for media_item in result.media
                    },
                    search_params=search_params,
                    page_info=result.page_info,
                ),
            )
        else:
            return InternalDirective.MAIN

    return action


def _create_recent_media_action(ctx: Context, state: State) -> MenuAction:
    def action():
        result = ctx.media_registry.get_recently_watched()
        if result:
            return State(
                menu_name=MenuName.RESULTS,
                media_api=MediaApiState(
                    search_result={
                        media_item.id: media_item for media_item in result.media
                    },
                    page_info=result.page_info,
                ),
            )
        else:
            return InternalDirective.MAIN

    return action


def _create_downloads_action(ctx: Context, state: State) -> MenuAction:
    """Create action to navigate to the downloads menu."""

    def action():
        return State(menu_name=MenuName.DOWNLOADS)

    return action


def _create_dynamic_search_action(ctx: Context, state: State) -> MenuAction:
    """Create action to navigate to the dynamic search menu."""

    def action():
        return State(menu_name=MenuName.DYNAMIC_SEARCH)

    return action

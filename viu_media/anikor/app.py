"""ANI.KOR home — the Textual app (tabs, keys, navigation, data refresh).

run_home(...) shows the dashboard and returns what the user picked:
    ("open", entry)   play/inspect this show in Viu (bridge.py hands off to MEDIA_ACTIONS)
    ("classic",)      Viu's old text main menu
    ("exit",)         quit Viu
Layout-specific widgets live in cards.py (option 1); this file is layout-agnostic.
"""
from __future__ import annotations

import logging
import os
import subprocess

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import ContentSwitcher, Input, Static

from . import data as D
from .cards import G, LAYOUTS, RICH, Item, Section, T, VScroll, section_title

logger = logging.getLogger(__name__)

TABS = [("home", G["home"], "Home"), ("profile", G["account"], "Profile"),
        ("mylist", G["bookmark"], "My List"), ("search", G["magnify"], "Search")]

LOGO = ("▄▀█ █▄ █ █   █▄▀ █▀█ █▀█",
        "█▀█ █ ▀█ █ ▄ █ █ █▄█ █▀▄")

# remembered across runs inside one Viu process (Viu -> back -> home restores the spot)
UI = {"tab": "home", "focus": {}, "list": "watching", "query": "", "dirty": False}

THEME = Theme(
    name="anikor", ansi=True, dark=True,
    primary="ansi_bright_magenta", secondary="ansi_magenta", accent="ansi_bright_red",
    warning="ansi_yellow", error="ansi_red", success="ansi_green",
    foreground="ansi_default", background="ansi_default", surface="ansi_default",
    panel="ansi_default", boost="ansi_default",
    variables={"text-muted": "ansi_bright_black", "footer-background": "ansi_default",
               "ansi-background": "ansi_default", "ansi-foreground": "ansi_default",
               "border-blurred": "ansi_bright_black",
               "input-cursor-background": "ansi_bright_magenta",
               "input-cursor-foreground": "ansi_black",
               "input-selection-background": "ansi_magenta",
               "block-cursor-background": "ansi_bright_magenta",
               "block-cursor-foreground": "ansi_black",
               "scrollbar": "ansi_bright_black", "scrollbar-hover": "ansi_magenta",
               "scrollbar-active": "ansi_bright_magenta", "scrollbar-background": "ansi_default",
               "scrollbar-background-hover": "ansi_default",
               "scrollbar-background-active": "ansi_default",
               "scrollbar-corner-color": "ansi_default"},
)


class TabLabel(Static):
    DEFAULT_CSS = """
    TabLabel { width: auto; height: 1; padding: 0 1; color: $text-muted; }
    TabLabel.-on { color: $primary; text-style: bold underline; }
    TabLabel:hover { color: $accent; }
    """

    def __init__(self, key, glyph, label, n):
        super().__init__(f"{glyph} {label} [dim]{n}[/]", id=f"tab-{key}", markup=True)
        self.key = key

    def on_click(self) -> None:
        self.app.switch_tab(self.key)


class UpdateButton(Static):
    """Big clickable UPDATE in the top bar; hidden until a newer release exists."""
    DEFAULT_CSS = """
    UpdateButton { display: none; width: auto; height: 2; padding: 0 2; margin: 0 2;
                   background: ansi_bright_magenta; color: ansi_black; text-style: bold;
                   content-align: center middle; }
    UpdateButton.-show { display: block; }
    UpdateButton:hover { background: ansi_bright_red; }
    """

    def on_click(self) -> None:
        self.app.action_update()


class AnikorApp(App):
    ENABLE_COMMAND_PALETTE = False
    AUTO_FOCUS = None
    CSS = """
    Screen { background: ansi_default; layers: base; }
    #top { height: 2; margin: 0 1; }
    #logo { width: 26; height: 2; color: $primary; }
    #topright { width: 1fr; height: 2; }
    #tabs { height: 1; align-horizontal: right; }
    #who { height: 1; content-align: right middle; color: $text-muted; }
    #rule { height: 1; margin: 0 1; color: $text-muted; }
    #pages { height: 1fr; margin: 0 0 0 1; }
    .page { height: 1fr; scrollbar-size-vertical: 1; }
    #page-profile { layout: horizontal; }
    .stats-col { width: 52; height: 1fr; padding: 0 2 0 0; }
    .upd-col { width: 1fr; height: 1fr; scrollbar-size-vertical: 1; }
    #chipbox { height: 2; }
    #listscroll, #searchscroll { height: 1fr; scrollbar-size-vertical: 1; }
    #q { height: 3; border: round $primary; background: ansi_default; padding: 0 1; margin: 0 1 0 0; }
    #q:focus { border: round $accent; }
    #bottom { height: 1; margin: 0 1; }
    #info { width: 1fr; height: 1; }
    #keys { width: auto; height: 1; color: $text-muted; }
    """

    BINDINGS = [
        Binding("tab", "back", "back", priority=True, show=False),
        Binding("shift+tab", "back", "back", priority=True, show=False),
        Binding("ctrl+q", "quit_viu", "quit", priority=True, show=False),
        Binding("up,k", "nav('up')", show=False),
        Binding("down,j", "nav('down')", show=False),
        Binding("left,h", "nav('left')", show=False),
        Binding("right,l", "nav('right')", show=False),
        Binding("enter", "pick_focused", show=False),
        Binding("1", "tab('home')", show=False),
        Binding("2", "tab('profile')", show=False),
        Binding("3", "tab('mylist')", show=False),
        Binding("4", "tab('search')", show=False),
        Binding("slash,s", "tab('search')", show=False),
        Binding("a", "add_plan", show=False),
        Binding("r", "reload", show=False),
        Binding("c", "classic", show=False),
        Binding("L", "toggle_layout", show=False),
        Binding("U", "update", show=False),
        Binding("pageup", "page('up')", show=False),
        Binding("pagedown", "page('down')", show=False),
    ]

    def __init__(self, cell, layout: str = "cards"):
        super().__init__(ansi_color=True)
        self.cell = cell
        self.layout = LAYOUTS.get(layout, LAYOUTS["cards"])(cell)
        self._pending: set[str] = set()
        self._search_results: list[dict] | None = None

    # ------------------------------------------------------------ data access
    def _path(self, name: str) -> str:
        if name in D.LIST_STATUSES:
            return D.list_path(name)
        return D.section_paths()[name]

    def _get(self, name: str):
        path = self._path(name)
        data, fresh = D.cached(path)
        if (not fresh or UI["dirty"]) and path not in self._pending and (
                UI["dirty"] or not D.recently_failed(path)):
            self._pending.add(path)
            fut = D.submit(D.fetch, path)
            fut.add_done_callback(lambda _f, n=name, p=path: self._fetched(n, p))
        return data

    def _fetched(self, name, path):
        self._pending.discard(path)
        if self.is_running:
            try:
                self.call_from_thread(self._apply_update, name)
            except Exception:  # noqa: BLE001  (app closed meanwhile)
                pass

    def home_entries(self, name: str) -> list[dict]:
        ents = D.entries(self._get(name))
        if name == "watching":
            return D.continue_watching(ents)
        return ents

    def profile_data(self):
        return D.profile(self._get("me"))

    # ------------------------------------------------------------ compose
    def compose(self) -> ComposeResult:
        with Horizontal(id="top"):
            yield Static(Text("\n".join(LOGO)), id="logo")
            yield UpdateButton("", id="update")
            with Vertical(id="topright"):
                with Horizontal(id="tabs"):
                    for i, (k, g, label) in enumerate(TABS, 1):
                        yield TabLabel(k, g, label, i)
                yield Static("", id="who")
        yield Static("", id="rule")
        with ContentSwitcher(id="pages", initial=f"page-{UI['tab']}"):
            yield VScroll(id="page-home", classes="page")
            yield Horizontal(id="page-profile", classes="page")
            with Vertical(id="page-mylist", classes="page"):
                yield Vertical(id="chipbox")
                yield VScroll(id="listscroll")
            with Vertical(id="page-search", classes="page"):
                yield Input(placeholder="search MyAnimeList…  (Enter)", id="q", value=UI["query"])
                yield VScroll(id="searchscroll")
        with Horizontal(id="bottom"):
            yield Static("", id="info")
            yield Static("↵ open · a +plan · / search · 1-4 tabs · tab back · c classic · ^q quit", id="keys")

    def on_mount(self) -> None:
        self.register_theme(THEME)
        self.theme = "anikor"
        self.title = "ANI.KOR"
        self._paint_logo()
        self._build_home()
        self._build_profile()
        self._build_mylist()
        self._build_search()
        self._paint_header()
        self.switch_tab(UI["tab"], restore=True)
        UI["dirty"] = False
        self._update_info = None
        self.run_worker(self._check_update, thread=True, exit_on_error=False)

    def _check_update(self) -> None:
        from . import update
        info = update.check()
        if info and self.is_running:
            self.call_from_thread(self._show_update, info)

    def _show_update(self, info: dict) -> None:
        self._update_info = info
        b = self.query_one("#update", UpdateButton)
        b.update(f"{G['download']} UPDATE\nv{info['current']} → v{info['latest']}")
        b.add_class("-show")
        self.notify(f"ANI.KOR v{info['latest']} is out — click UPDATE (or press U)", timeout=8)

    def action_update(self) -> None:
        if isinstance(self.focused, Input):
            return
        if getattr(self, "_update_info", None):
            self.exit(("update", self._update_info))

    def on_resize(self) -> None:
        self.query_one("#rule", Static).update(Text("─" * max(0, self.size.width - 2)))

    def _paint_logo(self) -> None:
        t = Text()
        for i, line in enumerate(LOGO):
            for ch_i, ch in enumerate(line):
                # the "." of ANI.KOR in pink, letters lavender
                t.append(ch, style=RICH["pink"] if 9 <= ch_i <= 11 else f"bold {RICH['lav']}")
            if i == 0:
                t.append("\n")
        self.query_one("#logo", Static).update(t)

    def _paint_header(self) -> None:
        p = self.profile_data()
        t = Text(justify="right")
        if p:
            t.append(f"{G['account']} ", style=RICH["pink"])
            t.append(p["name"], style="bold")
            t.append(f"  {G['play']} {p['watching']}  {G['bookmark']} {p['plan_to_watch']}  "
                     f"{G['check']} {p['completed']}  {G['clock']} {p['days']:.1f}d  "
                     f"{G['star']} {p['mean']:.2f}", style=RICH["dim"])
        self.query_one("#who", Static).update(t)

    # ------------------------------------------------------------ page builders
    def _replace_children(self, parent: Widget, widgets: list[Widget]) -> None:
        parent.remove_children()
        if widgets:
            parent.mount_all(widgets)

    def _build_home(self) -> None:
        self._replace_children(self.query_one("#page-home"), self.layout.home(self))

    def _build_profile(self) -> None:
        stats, upd = self.layout.profile(self)
        page = self.query_one("#page-profile")
        page.remove_children()
        page.mount(VScroll(stats, classes="stats-col"), VScroll(upd, classes="upd-col"))

    def _list_counts(self) -> dict:
        p = self.profile_data() or {}
        return {s: p.get(s) for s in D.LIST_STATUSES}

    def _build_mylist(self) -> None:
        self._replace_children(self.query_one("#chipbox"), [self.layout.chips(self._list_counts(), UI["list"])])
        self._build_list_grid()

    def _grid_width(self) -> int:
        return max(20, (self.size.width or 110) - 3)

    def _build_list_grid(self) -> None:
        s = UI["list"]
        ents = self.home_entries(s)
        data = D.cached(self._path(s))[0]
        empty = "loading…" if data is None else "Nothing on this list"
        mode = "progress" if s in ("watching", "on_hold", "dropped", "completed") else "season"
        g = self.layout.grid("list", None, ents, self._grid_width(), mode=mode, empty=empty)
        self._replace_children(self.query_one("#listscroll"), [g])

    def _build_search(self) -> None:
        ents = self._search_results
        if ents is None:
            title = section_title(G["magnify"], "Search", "type a title and press Enter")
            g = self.layout.grid("search", title, [], self._grid_width(), empty=" ")
        else:
            title = section_title(G["magnify"], f"Results for “{UI['query']}”", f"{len(ents)} shows")
            g = self.layout.grid("search", title, ents, self._grid_width(), empty="No results")
        self._replace_children(self.query_one("#searchscroll"), [g])

    def _apply_update(self, name: str) -> None:
        """A background fetch finished: rebuild what shows it, keep focus on the same show."""
        keep = self._focus_key()
        if name == "me":
            self._paint_header()
            self._build_profile()
            chips = self.query("#chipbox ChipRow")
            if chips:
                self._replace_children(self.query_one("#chipbox"),
                                       [self.layout.chips(self._list_counts(), UI["list"])])
        elif name == "recent":
            self._build_profile()
        elif name in D.LIST_STATUSES:
            if name == "watching":
                self._rebuild_home_section("cont")
            if name == UI["list"]:
                self._build_list_grid()
        else:
            key = {"season": "season", "suggestions": "sugg"}.get(name, "ranks")
            self._rebuild_home_section(key)
        self.call_after_refresh(self._restore_focus, keep)

    def _rebuild_home_section(self, key: str) -> None:
        page = self.query_one("#page-home")
        new = {s.key: s for s in self.layout.home(self)}.get(key)
        try:
            old = page.query_one(f".sec-{key}", Section)
        except Exception:  # noqa: BLE001
            return
        if new is None:
            return
        new.last_index = old.last_index
        page.mount(new, before=old)
        old.remove()

    # ------------------------------------------------------------ focus memory
    def _focus_key(self):
        f = self.focused
        if isinstance(f, Item):
            sec = self._section_of(f)
            return (sec.key if sec else None, f.entry.get("id") or f.entry.get("chip"))
        if isinstance(f, Input):
            return ("input", None)
        return None

    def _restore_focus(self, key) -> None:
        f = self.focused
        page = self.query_one(f"#page-{UI['tab']}")
        if f is not None and isinstance(f, (Item, Input)) and f.is_mounted and page in f.ancestors:
            if key is None or self._focus_key() == key:
                return
        if key and key[0] == "input":
            self.query_one("#q", Input).focus()
            return
        if key:
            for sec in self.sections():
                if sec.key != key[0]:
                    continue
                for r in sec.rows:
                    for it in r:
                        if (it.entry.get("id") or it.entry.get("chip")) == key[1]:
                            self._focus_item(it)
                            return
        self._focus_first()

    def _focus_first(self) -> None:
        for sec in self.sections():
            if sec.rows:
                r, c = sec.last_index if sec.remember else (0, 0)
                rows = sec.rows
                r = min(r, len(rows) - 1)
                c = min(c, len(rows[r]) - 1)
                self._focus_item(rows[r][c])
                return
        if UI["tab"] == "search":
            self.query_one("#q", Input).focus()

    # ------------------------------------------------------------ tabs
    def switch_tab(self, key: str, restore: bool = False) -> None:
        UI["tab"] = key
        self.query_one("#pages", ContentSwitcher).current = f"page-{key}"
        for k, *_ in TABS:
            self.query_one(f"#tab-{k}").set_class(k == key, "-on")
        if key == "search" and (self._search_results is None or not restore):
            self.call_after_refresh(self.query_one("#q", Input).focus)
        else:
            self.call_after_refresh(self._restore_focus, UI["focus"].get(key))

    def action_tab(self, key: str) -> None:
        if isinstance(self.focused, Input) and key != "search":
            return  # typing digits in search
        self.switch_tab(key)

    def action_back(self) -> None:
        """Tab = back: sub-page -> Home; Home -> hide the overlay (back to the game)."""
        if UI["tab"] != "home":
            self.switch_tab("home", restore=True)
            return
        # ANIKOR_HIDE_CMD: optional shell command run on Tab at Home (e.g. a window-manager
        # script that hides the ANI.KOR window). Without it, Tab at Home does nothing.
        hide = os.environ.get("ANIKOR_HIDE_CMD")
        if hide:
            subprocess.Popen(hide, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ------------------------------------------------------------ navigation
    def sections(self) -> list[Section]:
        page = self.query_one(f"#page-{UI['tab']}")
        return [s for s in page.query(Section) if s.rows]

    def _section_of(self, w: Widget):
        node = w
        while node is not None and not isinstance(node, Section):
            node = node.parent
        return node

    def _pos(self, item: Item):
        sec = self._section_of(item)
        if not sec:
            return None, -1, -1
        for r, row in enumerate(sec.rows):
            if item in row:
                return sec, r, row.index(item)
        return sec, -1, -1

    def _focus_item(self, it: Item) -> None:
        it.focus(scroll_visible=False)
        sec = self._section_of(it)
        page = self.query_one(f"#page-{UI['tab']}")

        def _scroll():
            it.scroll_visible(animate=False)
            # keep the section's title in view when the whole section fits
            vs = it.parent
            while vs is not None and not isinstance(vs, VerticalScroll):
                vs = vs.parent
            if sec is not None and vs is not None and sec.outer_size.height <= vs.size.height:
                vs.scroll_to_widget(sec, animate=False)
        self.call_after_refresh(_scroll)

    def focused_item_changed(self, it: Item) -> None:
        sec, r, c = self._pos(it)
        if sec is not None and r >= 0:
            sec.last_index = (r, c)
            UI["focus"][UI["tab"]] = (sec.key, it.entry.get("id") or it.entry.get("chip"))
        if "chip" in it.entry:
            if UI["list"] != it.entry["chip"]:
                UI["list"] = it.entry["chip"]
                for ch in self.query("Chip"):
                    ch.set_class(ch.status == UI["list"], "-on")
                self._build_list_grid()
            self._info(None)
            return
        self._info(it.entry)

    def _info(self, e) -> None:
        t = Text(no_wrap=True, overflow="ellipsis")
        if e:
            t.append(D.display_title(e), style=f"bold {RICH['lav']}")
            if e.get("en") and e["en"] != e["title"]:
                t.append(f"  {e['title']}", style=RICH["dim"])
            t.append(f"  {D.meta_line(e)}", style=RICH["dim"])
            if e.get("status"):
                t.append(f"  {D.STATUS_BADGE[e['status']]} {e.get('watched', 0)}/{e.get('eps') or '?'}",
                         style=RICH["pink"])
        self.query_one("#info", Static).update(t)

    def action_nav(self, d: str) -> None:
        f = self.focused
        secs = self.sections()
        if isinstance(f, Input):
            if d == "down" and secs:
                self._enter_section(secs[0], "down", None)
            return
        if not isinstance(f, Item):
            self._focus_first()
            return
        sec, r, c = self._pos(f)
        if sec is None or r < 0:
            self._focus_first()
            return
        rows = sec.rows
        if d in ("left", "right"):
            nc = c + (1 if d == "right" else -1)
            if 0 <= nc < len(rows[r]):
                self._focus_item(rows[r][nc])
            return
        nr = r + (1 if d == "down" else -1)
        if 0 <= nr < len(rows):
            self._focus_item(rows[nr][self._nearest(rows[nr], f)])
            return
        # leave the section
        try:
            i = secs.index(sec)
        except ValueError:
            return
        j = i + (1 if d == "down" else -1)
        if 0 <= j < len(secs):
            self._enter_section(secs[j], d, f)
        elif d == "up":
            if UI["tab"] == "search":
                self.query_one("#q", Input).focus()
            else:
                self.query_one(f"#page-{UI['tab']}").scroll_home(animate=False)
                if UI["tab"] == "profile":
                    self.query_one(".upd-col").scroll_home(animate=False)

    def _nearest(self, row: list[Item], ref: Widget | None) -> int:
        if ref is None or not row:
            return 0
        x = ref.region.x
        best, bi = None, 0
        for i, it in enumerate(row):
            if it.region.width == 0:
                continue
            dist = abs(it.region.x - x)
            if best is None or dist < best:
                best, bi = dist, i
        return bi

    def _enter_section(self, sec: Section, d: str, ref) -> None:
        rows = sec.rows
        if not rows:
            return
        r = 0 if d == "down" else len(rows) - 1
        if len(rows) == 1 and sec.remember:
            c = min(sec.last_index[1], len(rows[0]) - 1)
        else:
            c = self._nearest(rows[r], ref)
        self._focus_item(rows[r][c])

    def action_page(self, d: str) -> None:
        for _ in range(4):
            self.action_nav(d)

    # ------------------------------------------------------------ actions
    def pick(self, entry: dict) -> None:
        if "chip" in entry:
            return
        UI["dirty"] = True   # watching probably changes MAL progress — refetch on return
        self.exit(("open", entry))

    def action_pick_focused(self) -> None:
        f = self.focused
        if isinstance(f, Item):
            if "chip" in f.entry:
                rows = self.sections()
                if len(rows) > 1:
                    self._enter_section(rows[1], "down", None)
                return
            self.pick(f.entry)

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        q = ev.value.strip()
        if len(q) < 3:
            self.notify("type at least 3 letters", timeout=2)
            return
        UI["query"] = q
        self.query_one("#searchscroll").remove_children()
        self.query_one("#searchscroll").mount(Static(T(f"searching “{q}”…", RICH["dim"])))
        path = D.search_path(q)

        def done(fut):
            try:
                res = D.entries(fut.result())
            except Exception:  # noqa: BLE001
                res = []
            try:
                self.call_from_thread(self._search_done, q, res)
            except Exception:  # noqa: BLE001
                pass
        data, fresh = D.cached(path)
        if data is not None and fresh:
            self._search_done(q, D.entries(data))
        else:
            D.submit(D.fetch, path).add_done_callback(done)

    def _search_done(self, q, res) -> None:
        if q != UI["query"]:
            return
        self._search_results = res
        self._build_search()
        secs = self.sections()

        def go(tries=10):
            s = self.sections()
            if s:
                self._enter_section(s[0], "down", None)
            elif tries:
                self.set_timer(0.05, lambda: go(tries - 1))
        if res:
            self.call_after_refresh(go)

    def action_add_plan(self) -> None:
        f = self.focused
        if not isinstance(f, Item) or "id" not in f.entry:
            return
        e = f.entry
        if e.get("status"):
            self.notify(f"already on your list: {D.STATUS_NAME[e['status']]}", timeout=3)
            return
        title = D.display_title(e)

        def done(fut):
            ok = False
            try:
                ok = bool(fut.result())
            except Exception:  # noqa: BLE001
                pass
            try:
                self.call_from_thread(self._added, e, title, ok)
            except Exception:  # noqa: BLE001
                pass
        D.submit(D.add_to_plan, e["id"]).add_done_callback(done)

    def _added(self, e, title, ok) -> None:
        if not ok:
            self.notify(f"couldn't add {title}", severity="error", timeout=4)
            return
        e["status"] = "plan_to_watch"
        self.notify(f"{G['bookmark']} {title} → Plan to Watch", timeout=3)
        f = self.focused
        if isinstance(f, Item):
            f.refresh(recompose=True)
            self.call_after_refresh(f.focus)
        UI["dirty"] = True
        self._get("me")

    def action_reload(self) -> None:
        UI["dirty"] = True
        for n in ("season", "airing", "upcoming", "popular", "suggestions", "recent", "me", "watching", UI["list"]):
            self._get(n)
        UI["dirty"] = False
        self.notify("refreshing from MyAnimeList…", timeout=2)

    def action_classic(self) -> None:
        if isinstance(self.focused, Input):
            return
        self.exit(("classic",))

    def action_quit_viu(self) -> None:
        self.exit(("exit",))

    def action_toggle_layout(self) -> None:
        self.notify("layout 2 (text lists + preview) not built yet", timeout=3)


def run_home(layout: str | None = None):
    from textual_image._terminal import get_cell_size   # probes the terminal before Textual owns stdin
    import textual_image.widget  # noqa: F401 — sixel/kitty support probe, also before Textual starts
    try:
        cell = get_cell_size()
        cell = (cell.width or 8, cell.height or 17)
    except Exception:  # noqa: BLE001
        cell = (8, 17)
    layout = layout or _layout_pref()
    app = AnikorApp(cell, layout)
    return app.run(mouse=True)


def _layout_pref() -> str:
    try:
        from . import paths
        return (paths.CONFIG / "layout").read_text().strip() or "cards"
    except Exception:  # noqa: BLE001
        return "cards"

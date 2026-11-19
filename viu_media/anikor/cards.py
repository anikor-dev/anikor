"""ANI.KOR home — layout option 1: the MAL-style poster dashboard.

A *layout* turns data (lists of entries from data.py) into widgets. The app only calls:
    layout.home(app)        -> list[Section]   (top to bottom)
    layout.profile(app)     -> widget for the Profile tab
    layout.grid(entries, cols) -> Section      (My List / Search results)
Every pickable thing is an `Item` (has .entry); every block of items is a `Section` that
exposes `.rows` (row-major list of lists of Items) for arrow-key navigation.
Option 2 (clean text lists + one poster preview) can be another class with the same methods.
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, HorizontalScroll, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from . import data as D


class HScroll(HorizontalScroll, inherit_bindings=False, can_focus=False):
    """Horizontal poster strip; no own key bindings (arrows belong to ANI.KOR nav)."""


class VScroll(VerticalScroll, inherit_bindings=False, can_focus=False):
    """Vertical page scroller; no own key bindings, never takes focus."""

# Nerd Font Material glyphs (CaskaydiaCove NFM, verified with fontTools)
G = {
    "play": "\U000f040a", "bookmark": "\U000f00c0", "check": "\U000f012c", "pause": "\U000f03e4",
    "trash": "\U000f0a79", "fire": "\U000f0238", "star": "\U000f04ce", "account": "\U000f0004",
    "clock": "\U000f0954", "magnify": "\U000f0349", "plus": "\U000f0415", "trophy": "\U000f0538",
    "calendar": "\U000f00f0", "heart": "\U000f02d1", "home": "\U000f02dc", "download": "\U000f01da",
}
BADGE_GLYPH = {"watching": G["play"], "completed": G["check"], "on_hold": G["pause"],
               "dropped": G["trash"], "plan_to_watch": G["bookmark"]}
# ANSI palette slots (follow kitty theme / wallbash): lavender 13, pink 9, dim 8
BADGE_COLOR = {"watching": "ansi_bright_magenta", "completed": "ansi_blue", "on_hold": "ansi_yellow",
               "dropped": "ansi_cyan", "plan_to_watch": "ansi_bright_black"}
STAT_ORDER = ["watching", "completed", "on_hold", "dropped", "plan_to_watch"]
RICH = {"lav": "bright_magenta", "pink": "bright_red", "dim": "bright_black", "fg": "default"}
RICH_STATUS = {"watching": "bright_magenta", "completed": "blue", "on_hold": "yellow",
               "dropped": "cyan", "plan_to_watch": "bright_black"}


def T(s: str, style: str = "") -> Text:
    """Styled text as a span (a Text *base* style came out as truecolor, ignoring the kitty palette)."""
    t = Text()
    t.append(s, style=style)
    return t


def badge_text(e: dict) -> Text:
    s = e.get("status")
    if s:
        return T(f"{BADGE_GLYPH[s]} {D.STATUS_BADGE[s]}", RICH_STATUS[s])
    return T(f"{G['plus']} add", RICH["dim"])


# ---------------------------------------------------------------- poster
class Poster(Widget):
    """Poster thumbnail (textual-image picks kitty graphics / sixel / text blocks). Loads async; dim glyph until then."""

    DEFAULT_CSS = "Poster { width: 12; height: 8; } Poster > .ph { color: $text-muted; content-align: center middle; width: 100%; height: 100%; }"

    def __init__(self, entry: dict, w: int, h: int, **kw):
        super().__init__(**kw)
        self.entry, self.pw, self.ph = entry, w, h
        self.styles.width, self.styles.height = w, h
        self._shown = False

    def compose(self) -> ComposeResult:
        yield Static(T(G["play"], RICH["dim"]), classes="ph")

    def on_mount(self) -> None:
        f = D.poster_file(self.entry)
        if f.exists() and f.stat().st_size:
            self._show(f)
        else:
            app = self.app
            fut = D.submit(D.poster, self.entry)
            fut.add_done_callback(lambda fu: app.call_from_thread(self._loaded, fu) if app.is_running else None)

    def _loaded(self, fut) -> None:
        try:
            p = fut.result()
        except Exception:  # noqa: BLE001
            p = None
        if p and self.is_mounted:
            self._show(p)

    def _show(self, path: Path) -> None:
        if self._shown:
            return
        self._shown = True
        import os
        from textual_image.widget import Image, TGPImage
        # kitty: graphics protocol (what it supports best); elsewhere textual-image's pick
        # (made at startup in run_home): sixel on Windows Terminal, else text blocks
        kitty = os.environ.get("KITTY_WINDOW_ID") or os.environ.get("TERM") == "xterm-kitty"
        img = (TGPImage if kitty else Image)(str(path))
        img.styles.width, img.styles.height = self.pw, self.ph
        self.remove_children()
        self.mount(img)


# ---------------------------------------------------------------- items
class Item(Widget, can_focus=True):
    """Anything pickable. Enter/click -> app.pick(entry)."""

    def __init__(self, entry: dict, **kw):
        super().__init__(**kw)
        self.entry = entry

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.focus()
        self.app.pick(self.entry)

    def on_focus(self) -> None:
        self.app.focused_item_changed(self)


class PosterCard(Item):
    DEFAULT_CSS = """
    PosterCard { width: auto; height: auto; padding: 0 1 0 0; layout: vertical; }
    PosterCard > .bar { height: 1; color: $accent; }
    PosterCard > .title { height: 2; color: $foreground; }
    PosterCard > .meta { height: 1; }
    PosterCard:focus > .title { color: $primary; text-style: bold; }
    """

    def __init__(self, entry: dict, pw: int, ph: int, mode: str = "season", **kw):
        super().__init__(entry, **kw)
        self.pw, self.ph, self.mode = pw, ph, mode

    def compose(self) -> ComposeResult:
        e = self.entry
        yield Poster(e, self.pw, self.ph)
        yield Static("", classes="bar")
        t = Static(Text(D.display_title(e), overflow="ellipsis"), classes="title")
        t.styles.width = self.pw
        yield t
        m = Static(self._meta(), classes="meta")
        m.styles.width = self.pw
        yield m

    def _meta(self) -> Text:
        e = self.entry
        if self.mode == "progress":    # continue watching / my list: "Ep 3/24  ★8"
            t = Text()
            tot = e.get("eps") or "?"
            t.append(f"{e.get('watched', 0)}/{tot}", style=RICH["lav"])
            if e.get("score"):
                t.append(f"  {G['star']}{e['score']}", style=RICH["pink"])
            return t
        t = Text()
        if e.get("mean"):
            t.append(f"{G['star']}{e['mean']:.2f} ", style=RICH["pink"])
        t.append_text(badge_text(e))
        t.truncate(self.pw)
        return t

    def on_focus(self) -> None:
        self.query_one(".bar", Static).update(T("━" * self.pw, RICH["pink"]))
        super().on_focus()

    def on_blur(self) -> None:
        self.query_one(".bar", Static).update("")


class RankRow(Item):
    """'1  [poster]  Title / TV, 25 eps, scored 8.58 / 123,456 members   CMPL'"""

    DEFAULT_CSS = """
    RankRow { height: 3; width: 1fr; layout: horizontal; }
    RankRow > .mark { width: 1; height: 3; color: $accent; }
    RankRow > .rank { width: 3; height: 3; color: $primary; text-style: bold; }
    RankRow > Poster { margin: 0 1 0 0; }
    RankRow > .txt { width: 1fr; height: 3; }
    RankRow > .badge { width: 7; height: 3; content-align: right top; }
    RankRow:focus > .txt { text-style: bold; }
    """

    def __init__(self, entry: dict, pw: int, ph: int, **kw):
        super().__init__(entry, **kw)
        self.pw, self.ph = pw, ph

    def compose(self) -> ComposeResult:
        e = self.entry
        yield Static("", classes="mark")
        yield Static(str(e.get("rank") or ""), classes="rank")
        yield Poster(e, self.pw, self.ph)
        yield Static("", classes="txt")
        yield Static("", classes="badge")

    def on_mount(self) -> None:
        self._paint(False)

    def on_resize(self) -> None:
        self._paint(self.has_focus)

    def _paint(self, focused: bool) -> None:
        e = self.entry
        w = self.query_one(".txt", Static).size.width or 24
        t = Text()
        t.append_text(fit(D.display_title(e), w, f"bold {RICH['lav']}" if focused else "default"))
        t.append("\n")
        meta = Text()
        meta.append(f"{e['type'] or '?'} · {e['eps'] or '?'} eps", style="blue")
        if e.get("mean"):
            meta.append(f" · {G['star']}{e['mean']:.2f}", style=RICH["pink"])
        meta.truncate(w, overflow="ellipsis")
        t.append_text(meta)
        t.append("\n")
        t.append_text(fit(D.members(e), w, RICH["dim"]))
        self.query_one(".txt", Static).update(t)
        self.query_one(".badge", Static).update(badge_text(e))
        self.query_one(".mark", Static).update(T("▌\n▌\n▌", RICH["pink"]) if focused else "")

    def on_focus(self) -> None:
        self._paint(True)
        super().on_focus()

    def on_blur(self) -> None:
        self._paint(False)


def fit(s: str, w: int, style: str = "") -> Text:
    """One line, cut to w cells with an ellipsis."""
    t = Text(no_wrap=True)
    t.append(s, style=style)
    t.truncate(max(1, w), overflow="ellipsis")
    return t


class UpdateRow(Item):
    """Profile 'Last Anime Updates' row: poster, title, progress bar, 'Watching 3/24 · Scored -'."""

    DEFAULT_CSS = """
    UpdateRow { height: 4; width: 1fr; layout: horizontal; }
    UpdateRow > .mark { width: 1; height: 3; }
    UpdateRow > Poster { margin: 0 1 0 0; }
    UpdateRow > .txt { width: 1fr; height: 3; }
    """

    def __init__(self, entry: dict, pw: int, ph: int, **kw):
        super().__init__(entry, **kw)
        self.pw, self.ph = pw, ph

    def compose(self) -> ComposeResult:
        yield Static("", classes="mark")
        yield Poster(self.entry, self.pw, self.ph)
        yield Static("", classes="txt")

    def on_mount(self) -> None:
        self._paint(False)

    def on_resize(self) -> None:
        self._paint(self.has_focus)

    def _paint(self, focused: bool) -> None:
        e = self.entry
        w = max(10, self.query_one(".txt", Static).size.width or 40)
        s = e.get("status") or "watching"
        col = RICH_STATUS.get(s, "default")
        t = Text(no_wrap=True, overflow="ellipsis")
        t.append(D.display_title(e) + "\n", style=("bold " + RICH["lav"]) if focused else "default")
        tot, done = e.get("eps") or 0, e.get("watched") or 0
        frac = (done / tot) if tot else (1.0 if s == "completed" else 0.0)
        bw = max(6, w - 1)
        fill = int(round(frac * bw))
        t.append("━" * fill, style=col)
        t.append("━" * (bw - fill) + "\n", style=RICH["dim"])
        t.append(D.STATUS_NAME.get(s, s), style=col)
        t.append(f" {done}/{tot or '?'}", style="default")
        t.append(" · Scored ", style=RICH["dim"])
        t.append(str(e.get("score") or "-"), style=RICH["pink"] if e.get("score") else RICH["dim"])
        self.query_one(".txt", Static).update(t)
        self.query_one(".mark", Static).update(T("▌\n▌\n▌", RICH["pink"]) if focused else "")

    def on_focus(self) -> None:
        self._paint(True)
        super().on_focus()

    def on_blur(self) -> None:
        self._paint(False)


class Chip(Item):
    """My List status chip (entry = {'chip': status})."""

    DEFAULT_CSS = """
    Chip { width: auto; height: 1; padding: 0 1; color: $text-muted; }
    Chip.-on { color: $primary; text-style: bold; }
    Chip:focus { color: $accent; text-style: bold underline; }
    """

    def __init__(self, status: str, count: int | None, **kw):
        super().__init__({"chip": status}, **kw)
        self.status, self.count = status, count

    def render(self) -> Text:
        n = f" {self.count}" if self.count is not None else ""
        return Text(f"{BADGE_GLYPH[self.status]} {D.STATUS_NAME[self.status]}{n}")

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.focus()


# ---------------------------------------------------------------- sections
class Section(Vertical):
    """Titled block of Items; `.rows` drives arrow navigation."""

    DEFAULT_CSS = """
    Section { height: auto; margin: 0 0 1 0; }
    Section > .stitle { height: 1; color: $primary; text-style: bold; }
    Section > .empty { height: 1; color: $text-muted; }
    """
    remember = True   # come back to the same item when re-entering

    def __init__(self, key: str, title: str | Text | None, **kw):
        super().__init__(classes=f"sec-{key}", **kw)
        self.key, self.title_text = key, title
        self.last_index = (0, 0)

    @property
    def rows(self) -> list[list[Item]]:
        return [r for r in self._rows() if r]

    def _rows(self) -> list[list[Item]]:
        return []

    def compose_title(self):
        if self.title_text is not None:
            yield Static(self.title_text if isinstance(self.title_text, Text)
                         else Text(self.title_text), classes="stitle")


def section_title(glyph: str, text: str, extra: str = "") -> Text:
    t = Text()
    t.append(f"{glyph} ", style=RICH["pink"])
    t.append(text, style=f"bold {RICH['lav']}")
    if extra:
        t.append(f"  {extra}", style=RICH["dim"])
    return t


class PosterRow(Section):
    DEFAULT_CSS = "PosterRow > HScroll { height: auto; scrollbar-size: 0 0; }"

    def __init__(self, key, title, entries, pw, ph, mode="season", empty="loading…", **kw):
        super().__init__(key, title, **kw)
        self.entries, self.pw, self.ph, self.mode, self.empty = entries, pw, ph, mode, empty

    def compose(self) -> ComposeResult:
        yield from self.compose_title()
        if not self.entries:
            yield Static(self.empty, classes="empty")
            return
        with HScroll():
            for e in self.entries:
                yield PosterCard(e, self.pw, self.ph, self.mode)

    def _rows(self):
        return [list(self.query(PosterCard))] if self.entries else []


class RankBlock(Section):
    """Top Airing / Top Upcoming / Most Popular side by side (MAL's ranking widgets)."""

    DEFAULT_CSS = """
    RankBlock > Horizontal { height: auto; }
    RankBlock .col { width: 1fr; height: auto; padding: 0 1 0 0; }
    RankBlock .ctitle { height: 1; }
    """

    def __init__(self, key, cols: list[tuple[str, str, list[dict]]], pw, ph, **kw):
        super().__init__(key, None, **kw)
        self.cols, self.pw, self.ph = cols, pw, ph

    def compose(self) -> ComposeResult:
        with Horizontal():
            for i, (glyph, title, ents) in enumerate(self.cols):
                with Vertical(classes="col"):
                    yield Static(section_title(glyph, title), classes="ctitle")
                    if not ents:
                        yield Static(T("loading…", RICH["dim"]), classes="ctitle")
                    for e in ents:
                        yield RankRow(e, self.pw, self.ph)

    def _rows(self):
        colitems = [list(c.query(RankRow)) for c in self.query(".col")]
        n = max((len(c) for c in colitems), default=0)
        return [[c[r] for c in colitems if r < len(c)] for r in range(n)] if n else []


class GridSection(Section):
    DEFAULT_CSS = "GridSection > .grow { height: auto; width: 100%; }"
    remember = False

    def __init__(self, key, title, entries, pw, ph, cols, mode="season", empty="Nothing here", **kw):
        super().__init__(key, title, **kw)
        self.entries, self.pw, self.ph, self.cols, self.mode, self.empty = entries, pw, ph, max(1, cols), mode, empty

    def compose(self) -> ComposeResult:
        yield from self.compose_title()
        if not self.entries:
            yield Static(T(self.empty, RICH["dim"]), classes="empty")
            return
        for i in range(0, len(self.entries), self.cols):
            with Horizontal(classes="grow"):
                for e in self.entries[i:i + self.cols]:
                    yield PosterCard(e, self.pw, self.ph, self.mode)

    def _rows(self):
        return [list(r.query(PosterCard)) for r in self.query(".grow")]


class ChipRow(Section):
    DEFAULT_CSS = "ChipRow > Horizontal { height: 1; }"

    def __init__(self, key, counts: dict, current: str, **kw):
        super().__init__(key, None, **kw)
        self.counts, self.current = counts, current

    def compose(self) -> ComposeResult:
        with Horizontal():
            for s in D.LIST_STATUSES:
                c = Chip(s, self.counts.get(s))
                if s == self.current:
                    c.add_class("-on")
                yield c

    def _rows(self):
        return [list(self.query(Chip))]


class UpdatesSection(Section):
    def __init__(self, key, title, entries, pw, ph, **kw):
        super().__init__(key, title, **kw)
        self.entries, self.pw, self.ph = entries, pw, ph

    def compose(self) -> ComposeResult:
        yield from self.compose_title()
        if not self.entries:
            yield Static(T("loading…", RICH["dim"]), classes="empty")
        for e in self.entries:
            yield UpdateRow(e, self.pw, self.ph)

    def _rows(self):
        return [[r] for r in self.query(UpdateRow)]


# ---------------------------------------------------------------- profile stats panel
class StatsPanel(Static):
    """MAL 'Anime Stats': Days / Mean Score, stacked colored bar, legend + totals."""

    DEFAULT_CSS = "StatsPanel { height: auto; width: 1fr; }"

    def __init__(self, prof: dict | None, **kw):
        super().__init__("", **kw)
        self.prof = prof

    def on_resize(self) -> None:
        self.update(self._render_stats(self.size.width or 50))

    def on_mount(self) -> None:
        self.update(self._render_stats(self.size.width or 50))

    def _render_stats(self, w: int) -> Text:
        p = self.prof
        t = Text()
        if not p:
            t.append("loading profile…", style=RICH["dim"])
            return t
        t.append(f"{G['account']} ", style=RICH["pink"])
        t.append(f"{p['name']}'s Profile\n\n", style=f"bold {RICH['lav']}")
        t.append("Anime Stats\n", style="bold underline")
        t.append("Days: ", style=RICH["dim"]); t.append(f"{p['days']:.1f}", style="bold")
        t.append("    Mean Score: ", style=RICH["dim"]); t.append(f"{p['mean']:.2f}\n\n", style=f"bold {RICH['pink']}")
        bw = max(10, min(w - 2, 60))
        total = sum(p[k] for k in STAT_ORDER) or 1
        segs, used = [], 0
        for k in STAT_ORDER:
            n = int(round(p[k] / total * bw)) if p[k] else 0
            if p[k] and n == 0:
                n = 1
            segs.append([k, n]); used += n
        segs[max(range(len(segs)), key=lambda i: segs[i][1])][1] += bw - used  # fix rounding
        for k, n in segs:
            t.append("█" * max(0, n), style=RICH_STATUS[k])
        t.append("\n\n")
        right = [("Total Entries", f"{p['total']:,}"), ("Rewatched", f"{p['rewatched']:,}"),
                 ("Episodes", f"{p['episodes']:,}"), ("", ""), ("", "")]
        half = max(20, bw // 2)
        for (k, (rl, rv)) in zip(STAT_ORDER, right):
            line = Text()
            line.append("● ", style=RICH_STATUS[k])
            line.append(D.STATUS_NAME[k], style="default")
            line.append(" " * max(1, half - 2 - len(D.STATUS_NAME[k]) - len(str(p[k]))))
            line.append(f"{p[k]:,}", style="bold")
            if rl:
                line.append("   ")
                line.append(rl, style=RICH["dim"])
                line.append(" " * max(1, bw - half - 3 - len(rl) - len(rv)))
                line.append(rv, style="bold")
            t.append_text(line); t.append("\n")
        return t


# ---------------------------------------------------------------- the layout
class CardsLayout:
    """Option 1 — poster dashboard."""

    name = "cards"

    def __init__(self, cell: tuple[int, int]):
        cw, ch = cell
        ratio = 225 / 318   # MAL poster w/h
        self.pw = 12
        self.ph = max(5, int(round(self.pw * cw / (ch * ratio))))
        self.spw = 4                                              # small poster (rank rows)
        self.sph = max(2, int(round(self.spw * cw / (ch * ratio))))
        if self.sph > 3:
            self.sph = 3
            self.spw = max(3, int(round(3 * ch * ratio / cw)))
        self.card_w = self.pw + 1

    def home(self, app) -> list[Section]:
        y, s = D.season_now()
        cw = app.home_entries("watching")
        return [
            PosterRow("cont", section_title(G["play"], "Continue Watching", "your Watching list"),
                      cw, self.pw, self.ph, mode="progress",
                      empty=T("nothing in Watching — press / to find something", RICH["dim"])),
            PosterRow("season", section_title(G["calendar"], f"{s.title()} {y} Anime"),
                      app.home_entries("season"), self.pw, self.ph),
            RankBlock("ranks", [(G["fire"], "Top Airing Anime", app.home_entries("airing")),
                                (G["clock"], "Top Upcoming Anime", app.home_entries("upcoming")),
                                (G["trophy"], "Most Popular Anime", app.home_entries("popular"))],
                      self.spw, self.sph),
            PosterRow("sugg", section_title(G["heart"], "My Anime Suggestions"),
                      app.home_entries("suggestions"), self.pw, self.ph),
        ]

    def profile(self, app) -> list[Widget]:
        prof = app.profile_data()
        upd = UpdatesSection("updates", section_title(G["clock"], "Last Anime Updates"),
                             app.home_entries("recent")[:8], self.spw, self.sph)
        return [StatsPanel(prof), upd]

    def grid(self, key, title, entries, width, mode="season", empty="Nothing here") -> GridSection:
        cols = max(1, (width - 1) // self.card_w)
        return GridSection(key, title, entries, self.pw, self.ph, cols, mode=mode, empty=empty)

    def chips(self, counts, current) -> ChipRow:
        return ChipRow("chips", counts, current)


LAYOUTS = {"cards": CardsLayout}

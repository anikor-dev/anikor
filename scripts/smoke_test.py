"""CI smoke test (runs on Windows + Linux against the installed wheel, no MyAnimeList login).

python scripts/smoke_test.py
"""
import asyncio
import importlib
import sys

for mod in ["viu_media.anikor.cli", "viu_media.anikor.app", "viu_media.anikor.update",
            "viu_media.anikor.winsetup", "viu_media.anikor.bridge", "viu_media.mal_sync",
            "viu_media.libs.provider.anime.anicli.provider",
            "viu_media.libs.selectors.fzf.selector",
            "viu_media.cli.interactive.menu.media.main",
            "viu_media.cli.interactive.menu.media.player_controls",
            "viu_media.cli.interactive.session"]:
    importlib.import_module(mod)
print("imports ok")

from viu_media.core.config.model import AppConfig  # noqa: E402

c = AppConfig()
assert c.general.provider.value == "anicli", c.general.provider
assert c.fzf.header_color == "ansi:13"
assert "ANI" not in c.fzf.header_ascii_art or "█" in c.fzf.header_ascii_art
print("defaults ok")

from viu_media.anikor import update  # noqa: E402

assert update._ver("0.10.0") > update._ver("0.9.9")
print("version", update.current())

from viu_media.libs.selectors.fzf.selector import _tty_quiet  # noqa: E402

_tty_quiet()   # must not crash on Windows (no termios)
print("tty helper ok")


async def dashboard():
    from viu_media.anikor import app as A
    a = A.AnikorApp((8, 17), "cards")
    async with a.run_test(size=(140, 40)) as pilot:
        await pilot.pause(2)
        await pilot.press("2", "3", "4", "1")
        await pilot.pause(0.5)
        await pilot.press("ctrl+q")
    print("dashboard ok:", a.return_value)

asyncio.run(dashboard())

try:   # the anime site may block cloud IPs: report, don't fail
    from viu_media.libs.provider.anime.anicli import scraper
    print("source search:", scraper.search("frieren")[:1])
except Exception as e:  # noqa: BLE001
    print("source search skipped:", e)
sys.exit(0)

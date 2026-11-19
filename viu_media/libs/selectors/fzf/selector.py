import logging
import os
import shutil
import subprocess

from rich.prompt import Prompt

from viu_media.core.utils import detect

from ....core.config import FzfConfig
from ....core.exceptions import ViuError
from ..base import BaseSelector

logger = logging.getLogger(__name__)


# ANIKOR (2026-11-18): emoji → Nerd Font Material glyphs, so menus look like waybar/fastfetch
NERD = {
    '🔘': '\U000f0521',
    '❌': '\U000f0156',
    '🎞️': '\U000f0230',
    '🏠': '\U000f02dc',
    '🚮': '\U000f0a79',
    '🔥': '\U000f0238',
    '🔔': '\U000f009a',
    '🔎': '\U000f0349',
    '🔂': '\U000f0459',
    '🔁': '\U000f0456',
    '📺': '\U000f040a',
    '📝': '\U000f03eb',
    '📑': '\U000f00c0',
    '📀': '\U000f0435',
    '💯': '\U000f0538',
    '💖': '\U000f02d1',
    '🎲': '\U000f049d',
    '🎬': '\U000f00f0',
    '🎥': '\U000f0381',
    '➕': '\U000f0415',
    '✨': '\U000f0ae2',
    '✅': '\U000f012c',
    '⏸️': '\U000f03e4',
    '⏭️': '\U000f04ad',
    '⏪': '\U000f045f',
    'ℹ️': '\U000f02fc',
    '🔙': '\U000f004d',
    '🔗': '\U000f0337',
    '🔍': '\U000f0232',
    '🔄': '\U000f04e6',
    '📽️': '\U000f0279',
    '📼': '\U000f0567',
    '📥': '\U000f01da',
    '📅': '\U000f00ed',
    '💿': '\U000f05ee',
    '💾': '\U000f0193',
    '💽': '\U000f048b',
    '👥': '\U000f0849',
    '🌐': '\U000f059f',
    '⭐': '\U000f04ce',
    '▶️': '\U000f040a',
    '↩️': '\U000f054c',
}


def _tty_quiet(clear=False):
    """ANI.KOR 2026-11-18: mouse reports were echoing as junk (^[[<65;51;10M) between menus.
    Turn terminal mouse reporting off, drop any queued input, optionally clear the screen."""
    import sys
    try:
        out = "\033[?1000l\033[?1002l\033[?1003l\033[?1006l\033[?1015l"
        if clear:
            out += "\033[2J\033[H"
        sys.stdout.write(out); sys.stdout.flush()
        if sys.platform != "win32":
            import termios
            termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except Exception:  # noqa: BLE001
        pass


class FzfSelector(BaseSelector):
    def __init__(self, config: FzfConfig):
        self.config = config
        self.executable = shutil.which("fzf")
        if not self.executable:
            raise ViuError("Please install fzf to use the fzf selector")

        os.environ["FZF_DEFAULT_OPTS"] = self.config.opts

        # 2026-11-18 ANIKOR: header_color "ansi:N" = a kitty theme slot, so the logo follows the wallpaper
        if config.header_color.startswith("ansi:"):
            _hc = f"\033[38;5;{config.header_color[5:]}m"
        else:
            _r, _g, _b = config.header_color.split(",")
            _hc = f"\033[38;2;{_r};{_g};{_b}m"
        self.header = "\n".join(
            [
                f"{_hc}{line}\033[0m"
                for line in config.header_ascii_art.replace("\t", "").split("\n")
            ]
        )

    def choose(self, prompt, choices, *, preview=None, header=None):
        # ANIKOR: show Nerd Font glyphs instead of emoji (every menu); map the pick back after
        shown = {}
        for c in choices:
            d = c
            for e, g in NERD.items():
                if c.startswith(e):
                    d = g + " " + c[len(e):].lstrip()
                    break
            shown[d] = c
        choices = list(shown)
        fzf_input = "\n".join(choices)
        # ANI.KOR: Tab = go back one menu, everywhere. --expect makes fzf print the
        # key that ended it on line 1; the session loop reads went_back and pops a menu.
        self.went_back = False

        commands = [
            self.executable,
            "--prompt",
            f"{prompt.title()}: ",
            "--header",
            self.header + ("\n" + header if header else ""),
            "--header-first",
            "--expect=tab",
        ]
        if preview:
            commands.extend(["--preview", preview])

        _tty_quiet(clear=True)
        result = subprocess.run(
            commands,
            input=fzf_input,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=detect.get_clean_env(),
        )
        _tty_quiet()
        if result.returncode != 0:
            return None
        key, _, picked = result.stdout.partition("\n")
        if key.strip() == "tab":
            self.went_back = True
            return None
        picked = picked.strip()
        return shown.get(picked, picked)

    def choose_multiple(self, prompt, choices, preview=None):
        """Enhanced multi-selection using fzf's --multi flag."""
        fzf_input = "\n".join(choices)

        commands = [
            self.executable,
            "--multi",
            "--prompt",
            f"{prompt.title()}: ",
            "--header",
            f"{self.header}\nPress TAB to select multiple items, ENTER to confirm",
            "--header-first",
        ]
        if preview:
            commands.extend(["--preview", preview])

        _tty_quiet(clear=True)
        result = subprocess.run(
            commands,
            input=fzf_input,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=detect.get_clean_env(),
        )
        _tty_quiet()
        if result.returncode != 0:
            return []

        # Split the output by newlines and filter out empty strings
        selections = [
            line.strip() for line in result.stdout.strip().split("\n") if line.strip()
        ]
        return selections

    def confirm(self, prompt, *, default=False):
        choices = ["Yes", "No"]
        default_choice = "Yes" if default else "No"
        result = self.choose(prompt, choices, header=f"Default: {default_choice}")
        return result == "Yes"

    def ask(self, prompt, *, default=None):
        # cleaner to use rich
        return Prompt.ask(prompt, default=default)
        # -- not going to be used --
        commands = [
            self.executable,
            "--prompt",
            f"{prompt.title()}: ",
            "--header",
            self.header,
            "--header-first",
            "--print-query",
        ]

        _tty_quiet(clear=True)
        result = subprocess.run(
            commands,
            input="",
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
        # The output contains the selection (if any) and the query on the last line
        lines = result.stdout.strip().splitlines()
        return lines[-1] if lines else (default or "")

    def search(
        self,
        prompt,
        search_command,
        *,
        preview=None,
        header=None,
        initial_query=None,
        initial_results=None,
    ):
        """Enhanced search using fzf's --reload flag for dynamic search."""
        # Build the header with optional custom header line
        display_header = self.header
        if header:
            display_header = f"{self.header}\n{header}"

        commands = [
            self.executable,
            "--prompt",
            f"{prompt.title()}: ",
            "--header",
            display_header,
            "--header-first",
            "--disabled",  # Disable local filtering - rely on external search command
            "--bind",
            f"change:reload({search_command})",
            "--ansi",
        ]

        # If there's an initial query, set it
        if initial_query:
            commands.extend(["--query", initial_query])
            # Only trigger reload on start if we don't have cached results
            if not initial_results:
                commands.extend(["--bind", f"start:reload({search_command})"])

        if preview:
            commands.extend(["--preview", preview])

        # Use cached results as initial input if provided (avoids network request)
        fzf_input = "\n".join(initial_results) if initial_results else ""

        _tty_quiet(clear=True)
        result = subprocess.run(
            commands,
            input=fzf_input,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=detect.get_clean_env(),
        )
        _tty_quiet()
        if result.returncode != 0:
            return None
        return result.stdout.strip()


if __name__ == "__main__":
    config = FzfConfig()
    selector = FzfSelector(config)
    choice = selector.ask("Hello dev :)")
    print(choice)
    choice = selector.confirm("Hello dev :)")
    print(choice)
    choice = selector.choose_multiple("What comes first", ["a", "b"])
    print(choice)
    choice = selector.choose("What comes first", ["a", "b"])
    print(choice)

"""The `anikor` command.

    anikor                 open ANI.KOR (poster dashboard; first run walks you through login)
    anikor login           link your MyAnimeList account (guided, step by step)
    anikor login status    are you linked?
    anikor update          install the newest ANI.KOR now
    anikor classic         the plain text menus instead of the dashboard
    anikor version         which version is installed
    anikor setup-windows   (Windows) recreate the shortcut + Windows Terminal profile
    anikor setup-linux     (Linux) recreate the app-menu entry + ANI.KOR's kitty window
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import webbrowser

REDIRECT = "http://localhost:8765/callback"
CREATE_APP = "https://myanimelist.net/apiconfig/create"
MY_APPS = "https://myanimelist.net/apiconfig"
HOMEPAGE = "https://github.com/anikor-dev/anikor"

P, L, D, B, R = "\033[95m", "\033[35m", "\033[90m", "\033[1m", "\033[0m"


# ---------------------------------------------------------------- clipboard (best effort)
def _clip_set(text: str) -> bool:
    cmds = []
    if sys.platform == "win32":
        cmds = [["clip"]]
    elif sys.platform == "darwin":
        cmds = [["pbcopy"]]
    else:
        cmds = [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-ib"]]
    for c in cmds:
        if shutil.which(c[0]):
            try:
                subprocess.run(c, input=text.encode(), check=True, timeout=5,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:  # noqa: BLE001
                continue
    return False


def _clip_get() -> str:
    if sys.platform == "win32":
        cmds = [["powershell", "-NoProfile", "-Command", "Get-Clipboard"]]
    elif sys.platform == "darwin":
        cmds = [["pbpaste"]]
    else:
        cmds = [["wl-paste", "-n"], ["xclip", "-o", "-selection", "clipboard"], ["xsel", "-ob"]]
    for c in cmds:
        if shutil.which(c[0]):
            try:
                r = subprocess.run(c, capture_output=True, text=True, timeout=8)  # noqa: S603
                if r.returncode == 0:
                    return r.stdout.strip()
            except Exception:  # noqa: BLE001
                continue
    return ""


def _client_id(text: str) -> str | None:
    m = re.search(r"\b([0-9a-f]{32})\b", text or "")
    return m.group(1) if m else None


def _ask(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)


def _step(n: int, text: str) -> None:
    print(f"\n{P}{B} Step {n} {R} {text}")


# ---------------------------------------------------------------- guided login
def login(arg: str | None = None) -> None:
    from .. import mal_sync

    if arg == "status":
        ok = mal_sync.logged_in() and mal_sync._req("GET", "/users/@me")
        print(f"Linked to MyAnimeList as {ok.get('name')}" if ok else "Not linked to MyAnimeList (run: anikor login)")
        return
    if arg and _client_id(arg):
        mal_sync.login(_client_id(arg))
        return

    print(f"""
{P}{B}  ANI.KOR × MyAnimeList{R}

  ANI.KOR keeps your MyAnimeList up to date while you watch.
  To do that, MyAnimeList wants you to make a free "Client ID" — a key that is
  yours only. It takes about 2 minutes and you only do it once.
  {D}(You need a MyAnimeList account. If you don't have one, make it first.){R}""")
    if mal_sync.logged_in():
        me = mal_sync._req("GET", "/users/@me")
        if me and _ask(f"\n  Already linked as {B}{me.get('name')}{R}. Link again? [y/N] ").strip().lower() != "y":
            return

    _step(1, "Your browser will open MyAnimeList's \"Create ID\" page.")
    print(f"   If MyAnimeList asks you to log in, log in, then come back to that page:\n   {D}{CREATE_APP}{R}")
    _ask(f"\n   Press {B}Enter{R} to open it… ")
    webbrowser.open(CREATE_APP)

    copied = _clip_set(REDIRECT)
    _step(2, "Fill in the form like this:")
    print(f"""
     App Name ............ ANI.KOR (plus any word, e.g. ANI.KOR-yourname)
     App Type ............ {B}other{R}
     App Description ..... watching anime and syncing my list
     App Redirect URL .... {B}{REDIRECT}{R}   {P}{'← already copied: just press Ctrl+V' if copied else '← type this exactly'}{R}
     Homepage URL ........ {HOMEPAGE}
     Commercial / Non-Commercial ... {B}non-commercial{R}
     Name / Company Name . your MyAnimeList username
     Purpose of Use ...... {B}hobbyist{R}

   Tick the box to agree, then click {B}Submit{R}.""")

    _step(3, f"On the next page click {B}Edit{R} next to your new app.")
    print(f"   You'll see a {B}Client ID{R} (32 letters and numbers).")
    print(f"   {B}Select it and copy it{R} (Ctrl+C).  {D}Your apps live here: {MY_APPS}{R}")

    cid = None
    while not cid:
        typed = _ask(f"\n   Copied it? Press {B}Enter{R}  (or paste it here and press Enter): ").strip()
        cid = _client_id(typed.lower()) or _client_id(_clip_get().lower())
        if not cid:
            print(f"   {P}That doesn't look like a Client ID yet{R} — it's 32 characters, only 0-9 and a-f.")
            print("   Copy the Client ID from the MyAnimeList page and try again.")
    print(f"   Got it: {D}{cid[:6]}…{cid[-4:]}{R}")

    _step(4, f"Your browser will now ask you to let ANI.KOR use your list — click {B}Allow{R}.")
    time.sleep(1)
    mal_sync.login(cid)
    print(f"\n   {P}All done!{R} ANI.KOR is opening…\n")
    time.sleep(1.5)


# ---------------------------------------------------------------- run
def _viu(*args: str) -> None:
    from ..cli import run_cli
    sys.argv = ["anikor", *args]
    run_cli()


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0].lower() if args else ""
    if cmd in ("-h", "--help", "help"):
        print(__doc__)
        return
    if cmd in ("version", "--version", "-v"):
        from .update import current
        print(f"ANI.KOR {current()}")
        return
    if cmd == "login":
        login(args[1] if len(args) > 1 else None)
        return
    if cmd == "update":
        from . import update
        if update.is_dev_install():
            print("This is a developer copy (editable install): update it with git instead.")
            return
        print(update.start(update.check(max_age=0)))
        return
    if cmd == "setup-windows":
        from .winsetup import setup
        sys.exit(setup(quiet="--quiet" in args))
    if cmd == "setup-linux":
        from .linuxsetup import setup
        sys.exit(setup(quiet="--quiet" in args))
    if cmd == "classic":
        _viu("anilist", *args[1:])
        return
    if cmd:
        _viu(*args)   # anything else: plain Viu subcommands (anikor anilist search -t ..., etc.)
        return

    from .. import mal_sync
    if not mal_sync.logged_in():
        print(f"\n{P}{B}  Welcome to ANI.KOR!{R}  First, let's link your MyAnimeList.")
        login()
        if not mal_sync.logged_in():
            return
    os.environ["ANIKOR_HOME"] = "1"
    _viu("anilist")


if __name__ == "__main__":
    main()

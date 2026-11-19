# ANI.KOR

A MyAnimeList-style anime dashboard for your terminal: poster rows for **Continue Watching**,
this season, top airing and your lists. Pick a show, press Enter, watch it in mpv, and
your MyAnimeList updates by itself.

Built on [Viu](https://github.com/viu-media/viu) (archived), with a working anime source,
MyAnimeList sync and a new poster home screen.

## Windows: install

1. Click **Start**, type `PowerShell`, open **Windows PowerShell** (normal, *not* "Run as administrator").
2. Paste this and press **Enter**:
   ```
   irm https://raw.githubusercontent.com/anikor-dev/anikor/main/windows/install.ps1 | iex
   ```
3. Wait about 5 minutes until it says **ANI.KOR is installed!**

(There's also a double-click [Install.ANI.KOR.bat](https://github.com/anikor-dev/anikor/releases/latest/download/Install.ANI.KOR.bat),
but Windows 11's *Smart App Control* blocks downloaded .bat files. The PowerShell line avoids that download.)

Then double-click **ANI.KOR** on your desktop. The first time, it walks you through linking
your MyAnimeList (about 2 minutes, once). Full beginner walkthrough with every click:
**[docs/SETUP-GUIDE.md](docs/SETUP-GUIDE.md)**.

**Updates are one click.** When a new version is out, a pink **UPDATE** button appears at
the top of ANI.KOR. Click it (or press U) and it updates and reopens. Nothing updates by itself.

## Keys

| Key | What it does |
|---|---|
| arrows (or h j k l) | move around |
| Enter (or click) | open a show: play, pick an episode, change your list |
| Tab | go back |
| 1 2 3 4 | Home, Profile, My List, Search |
| / | search |
| a | add the selected show to Plan to Watch |
| r | refresh from MyAnimeList |
| U | update (when the UPDATE button shows) |
| Ctrl+Q | quit |

While a video plays: Space pause, ←/→ seek, f fullscreen, q close the video.

## Linux / macOS

Needs `mpv`, `fzf`, [uv](https://docs.astral.sh/uv/) and a Nerd Font. kitty shows the sharpest posters.

```sh
uv tool install --python 3.12 https://github.com/anikor-dev/anikor/releases/download/vX.Y.Z/anikor-X.Y.Z-py3-none-any.whl
anikor login     # link MyAnimeList (guided)
anikor           # open the dashboard
```

## Commands

```
anikor                 open ANI.KOR
anikor login           link MyAnimeList (guided)   ·   anikor login status
anikor update          install the newest version now
anikor classic         Viu's plain text menus
anikor version
```

## Where your stuff lives

Your MyAnimeList login, settings and cache are kept **outside** the install, so updates
never touch them:

- Windows: `%LOCALAPPDATA%\viu` (login + settings) and `%LOCALAPPDATA%\ANI.KOR` (launcher)
- Linux: `~/.config/viu`, `~/.cache/viu`, `~/.cache/anikor`

## Credits

- [Viu](https://github.com/viu-media/viu) by viu-media: the whole menu/player engine (Unlicense).
  Its original README is in [docs/VIU-README.md](docs/VIU-README.md).
- The anime source follows the same steps as [ani-cli](https://github.com/pystardust/ani-cli).
- Dashboard: [Textual](https://textual.textualize.io/) + [textual-image](https://github.com/lnqs/textual-image).

ANI.KOR doesn't host anything. It's a browser for third-party sites, the same as Viu. See [DISCLAIMER.md](DISCLAIMER.md).
Released under the Unlicense, like Viu.

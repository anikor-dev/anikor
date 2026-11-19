# ANI.KOR setup guide (Windows, step by step)

No experience needed. It takes about 10 minutes the first time. After that you just
double-click the desktop icon.

**What you need:** a Windows 10 or 11 PC, internet, and a MyAnimeList account
(make one free at <https://myanimelist.net/register.php> if you don't have one).

---

## Part 1: Install (about 5 minutes)

1. Click this link: **<https://github.com/anikor-dev/anikor/releases/latest/download/Install.ANI.KOR.bat>**
   It downloads a small file called `Install.ANI.KOR.bat`.
   (If your browser asks whether to keep it, click **Keep**.)
2. Open your **Downloads** folder.
3. **Double-click** `Install.ANI.KOR.bat`.
4. Windows may show a blue box, **"Windows protected your PC"**.
   Click **More info**, then **Run anyway**. (It shows this for any file it doesn't know.)
5. A black window opens and starts installing. You'll see lines like `[ok] uv`, `[ok] mpv`.
   **Leave it open.** If something asks *"Do you want to allow…"*, click **Yes**.
6. When it says **ANI.KOR is installed!**, press any key to close the window.

You now have an **ANI.KOR** icon on your desktop (and in the Start menu).

## Part 2: Link MyAnimeList (about 2 minutes, only once)

1. Double-click **ANI.KOR** on the desktop.
2. It says *Welcome to ANI.KOR!* Press **Enter**. Your browser opens MyAnimeList's
   **"Create ID"** page. If it asks you to log in, log in, then open the page again.
3. Fill in the form. ANI.KOR shows you the same list:

   | Field | What to put |
   |---|---|
   | App Name | `ANI.KOR` plus any word, e.g. `ANI.KOR-sam` |
   | App Type | **other** |
   | App Description | `watching anime and syncing my list` |
   | App Redirect URL | click in the box and press **Ctrl+V** (ANI.KOR already copied it for you: `http://localhost:8765/callback`) |
   | Homepage URL | `https://github.com/anikor-dev/anikor` |
   | Commercial / Non-Commercial | **non-commercial** |
   | Name / Company Name | your MyAnimeList username |
   | Purpose of Use | **hobbyist** |

   Tick the agreement box and click **Submit**.
4. On the next page, click **Edit** next to your new app. You'll see **Client ID**
   (a long code of letters and numbers). **Select it and press Ctrl+C.**
5. Go back to the ANI.KOR window and press **Enter**. It reads the code by itself.
6. Your browser shows *"ANI.KOR would like to access your account"*. Click **Allow**.
7. The browser says *linked*. Close that tab. ANI.KOR opens with your lists.

## Part 3: Watch

- Move with the **arrow keys** (or the mouse), press **Enter** on a show.
- Pick **Stream**, then an episode. The video opens in its own window (mpv).
- When you finish an episode, your MyAnimeList updates by itself.
- **Tab** goes back. **Ctrl+Q** quits.

In the video window: **Space** pause · **←/→** skip back/forward · **f** fullscreen · **q** close.

## Updates

Nothing to do. Every time you open ANI.KOR it checks for a new version and installs
it first. If a new version comes out while ANI.KOR is open, a pink **UPDATE** button appears
at the top. Click it and ANI.KOR updates and reopens.

## If something goes wrong

| Problem | Fix |
|---|---|
| The installer window shows red text | Take a screenshot and send it. Running the installer again is always safe. |
| Icons look like empty boxes | Open ANI.KOR from the **desktop icon**, not from a normal PowerShell or Command Prompt window. |
| "Not linked to MyAnimeList" | Open Start, type `cmd`, press Enter, then type `anikor login` and press Enter. |
| A show won't play | Try another episode or try again later. The source site is sometimes down. |
| No desktop icon | Run the installer again. |

Your login and settings are kept separately from the program, so reinstalling or
updating never logs you out.

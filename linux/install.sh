#!/usr/bin/env bash
# ANI.KOR installer for Linux. Safe to run again any time.
#   curl -fsSL https://raw.githubusercontent.com/anikor-dev/anikor/main/linux/install.sh | bash
#
# Installs: kitty (the terminal ANI.KOR runs in), mpv, fzf, uv, the CaskaydiaCove Nerd Font,
# ANI.KOR from the latest GitHub release, then an app-menu entry that opens ANI.KOR in its
# own styled kitty window. Your own kitty.conf is never touched.
# Your data (MyAnimeList login, cache, settings) lives in ~/.config/viu + ~/.cache and is
# never touched by installs or updates.
set -euo pipefail
REPO=anikor-dev/anikor

say() { printf '  \033[95m%s\033[0m\n' "$*"; }
ok()  { printf '  \033[92m[ok]\033[0m %s\n' "$*"; }
die() { printf '\n  \033[91m%s\033[0m\n\n' "$*" >&2; exit 1; }
has() { command -v "$1" >/dev/null 2>&1; }

# Everything is inside main(), called on the last line: with `curl | bash` the shell only
# starts once the whole script has arrived, and nothing below can swallow the rest of it.
main() {
    [ "$(id -u)" -eq 0 ] && die "Please run this as your normal user, not root/sudo (it asks for your password when it needs it)."
    has curl || die "This needs curl. Install it with your package manager, then run this again."
    export PATH="$HOME/.local/bin:$HOME/.local/kitty.app/bin:$PATH"

    printf '\n  \033[95;1mANI.KOR installer\033[0m\n\n'

    # --- 1. mpv + fzf (+ tar/xz for the font) from the system package manager -------------
    missing=()
    has mpv || missing+=(mpv)
    has fzf || missing+=(fzf)
    has xz  || missing+=(xz)
    if [ ${#missing[@]} -gt 0 ]; then
        say "Installing ${missing[*]} (your password may be asked)..."
        if   has pacman;  then pkgs=("${missing[@]}"); sudo pacman -S --needed --noconfirm "${pkgs[@]}" </dev/null
        elif has apt-get; then pkgs=("${missing[@]/#xz/xz-utils}"); sudo apt-get update -qq </dev/null; sudo apt-get install -y "${pkgs[@]}" </dev/null
        elif has dnf;     then pkgs=("${missing[@]}"); sudo dnf install -y "${pkgs[@]}" </dev/null
        elif has zypper;  then pkgs=("${missing[@]}"); sudo zypper --non-interactive install "${pkgs[@]}" </dev/null
        elif has xbps-install; then pkgs=("${missing[@]}"); sudo xbps-install -Sy "${pkgs[@]}" </dev/null
        elif has apk;     then pkgs=("${missing[@]}"); sudo apk add "${pkgs[@]}" </dev/null
        else die "Couldn't find your package manager. Install: ${missing[*]} — then run this again."
        fi
    fi
    for c in mpv fzf; do has "$c" || die "Could not install $c. Install it yourself, then run this again."; done
    ok "mpv + fzf"

    # --- 2. kitty (needs 0.37+ for the cursor trail; else the official no-sudo build) ------
    kver() { "$1" --version 2>/dev/null | awk '{print $2}'; }
    newer() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }   # $1 >= $2
    if has kitty && newer "$(kver kitty)" 0.37.0; then
        ok "kitty $(kver kitty)"
    else
        say "Installing kitty (official build, into ~/.local/kitty.app)..."
        curl -fsSL https://sw.kovidgoyal.net/kitty/installer.sh | sh /dev/stdin launch=n >/dev/null 2>&1 || die "Could not install kitty."
        mkdir -p "$HOME/.local/bin"
        ln -sf "$HOME/.local/kitty.app/bin/kitty" "$HOME/.local/kitty.app/bin/kitten" "$HOME/.local/bin/"
        ok "kitty $(kver "$HOME/.local/kitty.app/bin/kitty")"
    fi

    # --- 3. uv (installs Python + ANI.KOR, no sudo) ------------------------------------------
    if ! has uv; then
        say "Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
    fi
    has uv || die "Could not install uv."
    ok "uv"

    # --- 4. the font ---------------------------------------------------------------------------
    if fc-list 2>/dev/null | grep -qi "CaskaydiaCove Nerd Font Mono"; then
        ok "font"
    else
        say "Installing the ANI.KOR font (CaskaydiaCove Nerd Font)..."
        fdir="$HOME/.local/share/fonts/CaskaydiaCoveNerdFont"
        tmp=$(mktemp -d)
        curl -fsSL -o "$tmp/f.tar.xz" https://github.com/ryanoasis/nerd-fonts/releases/latest/download/CascadiaCode.tar.xz
        mkdir -p "$fdir"
        tar -xJf "$tmp/f.tar.xz" -C "$tmp"
        find "$tmp" -name 'CaskaydiaCoveNerdFontMono-*.ttf' -exec cp {} "$fdir/" \;
        rm -rf "$tmp"
        fc-cache -f "$fdir" >/dev/null 2>&1 || true
        ok "font"
    fi

    # --- 5. ANI.KOR itself -----------------------------------------------------------------------
    say "Finding the newest ANI.KOR..."
    if [ -n "${ANIKOR_WHEEL:-}" ]; then   # testing a local build
        whl="$ANIKOR_WHEEL"; tag="(local build)"
    else
        json=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest")
        tag=$(grep -o '"tag_name": *"[^"]*"' <<<"$json" | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
        whl=$(grep -o '"browser_download_url": *"[^"]*\.whl"' <<<"$json" | head -1 | sed 's/.*"\(http[^"]*\)"$/\1/')
    fi
    [ -n "$whl" ] || die "The newest release ($tag) has no package file yet. Try again in a few minutes."
    say "Installing ANI.KOR $tag (downloads Python the first time)..."
    uv tool install --force --python 3.12 "$whl" >/dev/null 2>&1 || uv tool install --force --python 3.12 "$whl" \
        || die "Installing ANI.KOR failed."
    uv tool update-shell >/dev/null 2>&1 || true
    ok "ANI.KOR $tag"

    # --- 6. kitty look, launcher, app-menu entry (done by ANI.KOR itself) ---------------------
    anikor setup-linux || die "Setting up the app-menu entry failed."

    printf '\n  \033[95;1mANI.KOR is installed!\033[0m\n'
    echo   '  Open "ANI.KOR" from your app menu (or run: anikor-kitty). The first time, it walks'
    echo   '  you through linking your MyAnimeList (about 2 minutes).'
    echo
}

main "$@"

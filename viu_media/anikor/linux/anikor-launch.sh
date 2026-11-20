#!/usr/bin/env bash
# ANI.KOR launcher for Linux (the app-menu entry runs this inside ANI.KOR's kitty window).
# Never updates by itself: when a new version is out ANI.KOR shows an UPDATE button;
# clicking it quits back here with a flag file -> update -> reopen.
# Written by `anikor setup-linux`; refreshed automatically after each update.
HOME_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/anikor"
FLAG="$HOME_DIR/update-requested"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
export ANIKOR_LAUNCHER=1

update_anikor() {
    local json want have whl
    json=$(curl -fsSL --max-time 8 https://api.github.com/repos/anikor-dev/anikor/releases/latest) || {
        echo "  Could not reach GitHub to update. Opening the current version."; sleep 2; return; }
    want=$(grep -o '"tag_name": *"[^"]*"' <<<"$json" | head -1 | sed 's/.*"v\{0,1\}\([^"]*\)"$/\1/')
    whl=$(grep -o '"browser_download_url": *"[^"]*\.whl"' <<<"$json" | head -1 | sed 's/.*"\(http[^"]*\)"$/\1/')
    have=$(anikor version 2>/dev/null | sed 's/^ANI\.KOR *//')
    [ -n "$whl" ] && [ "$want" != "$have" ] || return
    printf '\n  \033[95mUpdating ANI.KOR  v%s  ->  v%s ...\033[0m\n' "$have" "$want"
    if uv tool install --force --python 3.12 "$whl" >/dev/null 2>&1; then
        anikor setup-linux --quiet >/dev/null 2>&1
        printf '  \033[92mUpdated!\033[0m\n'
    else
        echo "  Update failed - opening the version you have."
    fi
    sleep 1
}

[ "$1" = "--update" ] && update_anikor
while true; do
    rm -f "$FLAG"
    anikor
    [ -f "$FLAG" ] || break
    update_anikor
    # the launcher itself may have been refreshed by the update: run the new one
    exec "$HOME_DIR/anikor-launch.sh"
done

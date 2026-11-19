#!/usr/bin/env bash
# Ship a new ANI.KOR version to everyone:   scripts/release.sh 0.2.0 "what changed"
# 1. bumps the version  2. adds the notes to CHANGELOG.md  3. privacy scan  4. test build
# 5. commits + tags + pushes  6. publishes the GitHub release (wheel + Windows installer). Installed copies pick it up on their next launch (or via the UPDATE button).
set -euo pipefail
export TZ=UTC   # commit times don't reveal the local timezone
cd "$(git rev-parse --show-toplevel)"
v="${1:-}"; notes="${2:-}"
if ! [[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || [ -z "$notes" ]; then
    echo 'usage: scripts/release.sh X.Y.Z "what changed"' >&2; exit 2
fi
git rev-parse -q --verify "refs/tags/v$v" >/dev/null && { echo "v$v already exists" >&2; exit 1; }
old=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)
[ "$(printf '%s\n%s\n' "$old" "$v" | sort -V | tail -1)" = "$v" ] && [ "$old" != "$v" ] || { echo "v$v is not newer than $old" >&2; exit 1; }

sed -i "0,/^version = \".*\"/s//version = \"$v\"/" pyproject.toml
{ printf '# Changelog\n\n## v%s (%s)\n\n%s\n\n' "$v" "$(date +%F)" "$notes"; sed '1{/^# Changelog$/d}' CHANGELOG.md | sed '1{/^$/d}'; } > CHANGELOG.md.new
mv CHANGELOG.md.new CHANGELOG.md

rm -rf dist && uv build -q
uv run --no-project --with dist/anikor-"$v"-py3-none-any.whl --python 3.12 python -c \
    "import viu_media.anikor.app, viu_media.anikor.cli, viu_media.libs.provider.anime.anicli.provider; print('import ok')"
git add -A
scripts/privacy-scan.sh
git commit -qm "Release v$v" -m "$notes"
git tag -a "v$v" -m "ANI.KOR v$v"
git push -q origin main "v$v"
scripts/publish.sh "v$v"

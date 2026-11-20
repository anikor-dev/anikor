#!/usr/bin/env bash
# Publish the GitHub release for an existing tag (used by release.sh; safe to rerun):
#   scripts/publish.sh v0.1.0
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
tag="$1"; v="${tag#v}"
GH="$(command -v gh || echo "$HOME/.local/bin/gh")"
git checkout -q "$tag" -- pyproject.toml
rm -rf dist && uv build -q
uv run -q --no-project --with "dist/anikor-$v-py3-none-any.whl" --python 3.12 python scripts/smoke_test.py >/dev/null
scripts/privacy-scan.sh
notes=$(mktemp)
awk -v h="## v$v " 'index($0,h)==1{on=1;next} /^## v/{on=0} on' CHANGELOG.md > "$notes"
printf '\n---\n**New here? (Windows)** Download **Install.ANI.KOR.bat** below and double-click it. [Step-by-step guide](https://github.com/anikor-dev/anikor/blob/main/docs/SETUP-GUIDE.md)\n' >> "$notes"
printf '\n**Linux:** paste in a terminal: `curl -fsSL https://raw.githubusercontent.com/anikor-dev/anikor/main/linux/install.sh | bash`\n' >> "$notes"
cp "windows/Install ANI.KOR.bat" "dist/Install.ANI.KOR.bat"
"$GH" release create "$tag" "dist/anikor-$v-py3-none-any.whl" "dist/Install.ANI.KOR.bat" \
    --repo anikor-dev/anikor --title "ANI.KOR $tag" --notes-file "$notes"
rm -f "$notes"

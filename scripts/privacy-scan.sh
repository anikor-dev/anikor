#!/usr/bin/env bash
# Refuse to publish anything personal. Scans: every tracked/untracked file, every commit
# (author, committer, message, full diff of all history) and any built wheel in dist/.
# The patterns are NOT in this repo (that would publish them): one extended regex per line in
#   ${ANIKOR_PRIVATE_PATTERNS:-~/.config/anikor-private/patterns}
# Runs automatically before every `git push` (pre-push hook) and in scripts/release.sh.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
PAT="${ANIKOR_PRIVATE_PATTERNS:-$HOME/.config/anikor-private/patterns}"
if [ ! -s "$PAT" ]; then
    echo "privacy-scan: no pattern file at $PAT — refusing (create it, one regex per line)" >&2
    exit 1
fi
mapfile -t pats < <(grep -v '^\s*#' "$PAT" | sed '/^\s*$/d')
fail=0
hit() { echo "  ✗ $1" >&2; fail=1; }
for p in "${pats[@]}"; do
    # 1. files in the working tree (tracked + untracked, minus .gitignore'd)
    while IFS= read -r f; do hit "file: $f"; done < <(git ls-files -co --exclude-standard -z | xargs -0 grep -I -l -i -E -e "$p" -- 2>/dev/null)
    # 1b. file NAMES
    git ls-files -co --exclude-standard | grep -i -E -q -e "$p" && hit "a file name matches"
    # 2. commit metadata + messages + every diff in history (all branches/tags)
    if git rev-parse -q --verify HEAD >/dev/null; then
        git log --all --format='%an%n%ae%n%cn%n%ce%n%B' | grep -i -E -q -e "$p" && hit "commit author/committer/message"
        git log --all -p --format= | grep -i -E -q -e "$p" && hit "something in commit history (git log -p)"
    fi
    # 3. built packages
    for w in dist/*.whl dist/*.tar.gz; do
        [ -e "$w" ] || continue
        python3 - "$w" "$p" <<'PY' || hit "inside $w"
import re, sys, tarfile, zipfile
path, pat = sys.argv[1], re.compile(sys.argv[2].encode(), re.I)
if path.endswith(".whl"):
    z = zipfile.ZipFile(path); blobs = [(n, z.read(n)) for n in z.namelist()]
else:
    t = tarfile.open(path); blobs = [(m.name, t.extractfile(m).read()) for m in t.getmembers() if m.isfile()]
bad = [n for n, b in blobs if pat.search(b) or pat.search(n.encode())]
sys.exit(1 if bad else 0)
PY
    done
done
if [ $fail -ne 0 ]; then
    echo "privacy-scan: FOUND personal info (pattern hits above). Nothing was pushed." >&2
    exit 1
fi
echo "privacy-scan: clean (${#pats[@]} patterns; files, $(git rev-list --all --count 2>/dev/null || echo 0) commits, dist/)"

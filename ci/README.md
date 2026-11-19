# GitHub Actions (parked)

`ci.yml` (Windows + Linux smoke test on every push) and `release.yml` (tag -> release) are
kept here because pushing files under `.github/workflows/` needs a GitHub token with the
`workflow` scope. To turn them on: on github.com open the repo -> Add file -> Create new
file -> name it `.github/workflows/ci.yml`, paste the contents, commit (same for
release.yml). Until then `scripts/release.sh` builds and publishes releases locally.

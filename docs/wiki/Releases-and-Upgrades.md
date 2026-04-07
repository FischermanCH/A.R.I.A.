# Releases and Upgrades

ARIA currently uses a simple release model:

- code on GitHub
- tagged public alpha releases
- Docker Hub images
- internal alpha TAR builds for fast local testing

Current release principles:

- public release notes are maintained in `CHANGELOG.md`
- Docker tags follow public alpha tags
- internal builds can move faster than public tags
- in-app update execution is intentionally not built yet

Useful references:

- [`CHANGELOG.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/CHANGELOG.md)
- [`docs/release/versioning.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/release/versioning.md)
- [`docs/release/github-release-notes-template.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/release/github-release-notes-template.md)

Quick checks:

- `aria --version` zeigt die lokal installierte ARIA-Release-Kennung
- `aria version-check` vergleicht die installierte Version mit dem neuesten oeffentlichen Release
- nach staerkeren UI-/CSS-Updates kann ein harter Browser-Reload sinnvoll sein, falls ein Browser noch alte Assets aus dem Cache zeigt

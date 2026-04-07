# Releases and Upgrades

ARIA nutzt aktuell ein einfaches Release-Modell:

- Code auf GitHub
- getaggte oeffentliche Alpha-Releases
- Docker-Hub-Images
- interne Alpha-TAR-Builds fuer schnelles lokales Testen

Aktuelle Release-Prinzipien:

- oeffentliche Release Notes werden in `CHANGELOG.md` gepflegt
- Docker-Tags folgen den oeffentlichen Alpha-Tags
- interne Builds koennen schneller laufen als Public-Tags
- ein direktes In-App-Update ist bewusst noch nicht eingebaut

Nuetzliche Referenzen:

- [`CHANGELOG.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/CHANGELOG.md)
- [`docs/release/versioning.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/release/versioning.md)
- [`docs/release/github-release-notes-template.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/release/github-release-notes-template.md)

Schnelle Checks:

- `aria --version` zeigt die lokal installierte ARIA-Release-Kennung
- `aria version-check` vergleicht die installierte Version mit dem neuesten oeffentlichen Release
- nach staerkeren UI-/CSS-Updates kann ein harter Browser-Reload sinnvoll sein, falls ein Browser noch alte Assets aus dem Cache zeigt

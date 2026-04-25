# Releases and Upgrades

ARIA nutzt aktuell ein einfaches Release-Modell:

- Code auf GitHub
- getaggte oeffentliche Alpha-Releases
- Docker-Hub-Images
- interne Alpha-TAR-Builds fuer schnelles lokales Testen

Aktuelle Release-Prinzipien:

- oeffentliche Release Notes werden in `CHANGELOG.md` gepflegt
- Docker-Tags folgen den oeffentlichen Alpha-Tags
- interne TAR-Wege duerfen sich als Transportweg unterscheiden, aber die sichtbare ARIA-Release-Kennung soll auf derselben veroeffentlichten Code-Linie bleiben
- ein direktes In-App-Update ist bewusst noch nicht eingebaut
- der bevorzugte frische Docker-Installationsweg ist jetzt `aria-setup`, das ein kontrolliertes Compose-Verzeichnis mit vorhersagbaren Update-Befehlen anlegt

Nuetzliche Referenzen:

- [`CHANGELOG.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/CHANGELOG.md)
- [`docs/release/versioning.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/release/versioning.md)
- [`docs/release/github-release-notes-template.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/release/github-release-notes-template.md)

Schnelle Checks:

- `aria --version` zeigt die lokal installierte ARIA-Release-Kennung
- `aria version-check` vergleicht die installierte Version mit dem neuesten oeffentlichen Release
- nach staerkeren UI-/CSS-Updates kann ein harter Browser-Reload sinnvoll sein, falls ein Browser noch alte Assets aus dem Cache zeigt

Host-seitiger Upgrade-Helper:

- `docker/aria-host-update.sh detect` listet Compose-basierte ARIA-Stacks auf dem Host, inklusive Projektname, Port, Health und Modus (`internal-local` oder Registry)
- `docker/aria-host-update.sh update --project <name> --dry-run` zeigt den geplanten Update-Weg ohne Aenderungen
- `docker/aria-host-update.sh update --project <name>` aktualisiert gezielt nur den `aria`-Service dieses Projekts
- der Helper laesst `qdrant`, `searxng`, `valkey` und bestehende Volumes bewusst unangetastet
- fuer `aria:alpha-local` laedt er das neueste interne TAR; fuer Registry-Stacks nutzt er `docker compose pull aria`
- wenn ein Portainer-Stack seine Compose-Datei nicht hostseitig freigibt, kann der Helper optional ueber `PORTAINER_URL` und `PORTAINER_API_KEY` direkt mit der Portainer-API reden
- dafuer kann neben dem Script eine optionale `aria-host-update.env` liegen; Vorlage: `docker/aria-host-update.env.example`
- wenn weder lokale Stack-Datei noch Portainer-API verfuegbar sind, sollte die Compose-/Portainer-Stack-Datei explizit per `--stack-file <pfad>` angegeben werden

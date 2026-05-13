# Releases and Upgrades

Aktuelle Public Alpha: `0.1.0-alpha251`.

ARIA hat drei Update-Wege. Diese sollten sauber getrennt bleiben.

## 1. Managed Installs mit `aria-setup`

Das ist der bevorzugte Public-Pfad.

Typische Befehle:

```bash
cd /opt/aria/aria
./aria-stack.sh update
./aria-stack.sh health
./aria-stack.sh logs
```

Der normale `aria-stack.sh update` aktualisiert/recreatet nur den `aria` Service. Qdrant, SearXNG, Valkey und Volumes bleiben bewusst unangetastet.
Sobald ARIA danach wieder gesund ist, entfernen managed/interne Helper dangling Docker-Image-Layer und alte ungenutzte ARIA-Docker-Images. Container, Volumes, Sidecars und getaggte fremde Images werden nicht bereinigt.

Wenn ein Release das Stack-Layout selbst aendert:

```bash
aria-setup upgrade --install-dir /opt/aria/aria
```

`update-all` oder `repair` nur verwenden, wenn Release Notes oder Recovery-Hinweise es explizit verlangen.

Managed Installs koennen auch die Browser-Update-Seite unter `/updates` anbieten.

## 2. Manuelle Public-Docker-Compose-Installs

Normales Update:

```bash
docker compose -f docker-compose.public.yml pull aria
docker compose -f docker-compose.public.yml up -d --no-deps --force-recreate aria
```

Regeln:

- dasselbe Compose-File behalten
- denselben Compose-Projektnamen behalten
- dieselben Volumes behalten
- Host-seitige Docker-Kommandos nutzen, ausser der Stack enthaelt bewusst den Managed Helper

## 3. Interne lokale TAR-Builds

Dieser Pfad ist fuer interne Alpha-Tests:

- `aria-pull`
- `docker/update-local-aria.sh`
- `docker/portainer-stack.alpha3.local.yml`
- lokales Image `aria:alpha-local`

## Host-seitiger Upgrade-Helper

`docker/aria-host-update.sh` kann Compose-basierte ARIA-Stacks erkennen und aktualisieren.

Wichtige Befehle:

- `docker/aria-host-update.sh detect`
- `docker/aria-host-update.sh update --project <name> --dry-run`
- `docker/aria-host-update.sh update --project <name>`
- `docker/aria-host-update.sh update --project <name> --target-image fischermanch/aria:<version>`

Sicherheitsverhalten:

- aktualisiert nur den ausgewaehlten `aria` Service
- laesst Qdrant, SearXNG, Valkey und Volumes unangetastet
- aktualisiert Managed-Helper-Dateien aus dem Ziel-Image vor dem ARIA-Recreate
- prueft den geplanten Host-Port vor dem ARIA-Recreate
- bereinigt dangling Layer und alte ungenutzte ARIA-Images erst nach erfolgreichem Healthcheck
- bricht sicher ab, wenn ein anderer Prozess oder Container diesen Port belegt

## Schnelle Checks

- `aria --version`
- `aria version-check`
- `/stats` Preflight
- `/updates` Helper-Status bei Managed Installs
- harter Browser-Reload nach groesseren UI-/CSS-Updates

Referenzen:

- [`CHANGELOG.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/CHANGELOG.md)
- [`docs/release/versioning.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/release/versioning.md)
- [`docs/setup/setup-overview.md`](https://github.com/FischermanCH/A.R.I.A./blob/main/docs/setup/setup-overview.md)

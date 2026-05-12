# Releases and Upgrades

ARIA hat aktuell drei Update-Wege, die bewusst getrennt bleiben sollten.

## 1. Managed Installs mit `aria-setup`

Das ist der bevorzugte Public-Pfad.

Typische Befehle:

```bash
cd /opt/aria/aria
./aria-stack.sh update
./aria-stack.sh health
./aria-stack.sh logs
```

Der normale `aria-stack.sh update` aktualisiert und recreatet nur den `aria` Service. Stateful Sidecars wie Qdrant, SearXNG, Valkey und bestehende Volumes bleiben bewusst unangetastet.

Wenn ein Release das Stack-Layout selbst aendert, zum Beispiel durch einen neuen Sidecar-Service:

```bash
aria-setup upgrade --install-dir /opt/aria/aria
```

`./aria-stack.sh update-all` oder `./aria-stack.sh repair` nur verwenden, wenn Release Notes oder Recovery-Hinweise explizit Full-Stack-Arbeit verlangen.

Managed Installs koennen auch den kontrollierten Browser-Update-Pfad unter `/updates` nutzen.

## 2. Manuelle Public-Docker-Compose-Installs

Dieser Pfad nutzt:

- `docker-compose.public.yml`

Normales Update:

```bash
docker compose -f docker-compose.public.yml pull aria
docker compose -f docker-compose.public.yml up -d --no-deps --force-recreate aria
```

Regeln:

- dasselbe Compose-File behalten
- denselben Compose-Projektnamen behalten
- dieselben Volumes behalten
- `/updates` und Chat-Update gehoeren zum Managed-Install-Pfad

## 3. Interne lokale TAR-Builds

Dieser Pfad ist fuer schnelle interne Alpha-Tests.

Er nutzt:

- `aria-pull`
- `docker/update-local-aria.sh`
- `docker/portainer-stack.alpha3.local.yml`

Der lokale Update-Flow kann den `/updates` Button nutzen, wenn der Stack den `aria-updater` Helper enthaelt.

## Host-seitiger Upgrade-Helper

- `docker/aria-host-update.sh detect` listet Compose-basierte ARIA-Stacks auf dem Host, inklusive Projektname, Port, Health und Modus (`internal-local` oder Registry)
- `docker/aria-host-update.sh update --project <name> --dry-run` zeigt den geplanten Update-Weg ohne Aenderungen
- `docker/aria-host-update.sh update --project <name>` aktualisiert gezielt nur den `aria` Service dieses Projekts
- `docker/aria-host-update.sh update --project <name> --target-image fischermanch/aria:<version>` hebt einen gepinnten alten Stack gezielt auf ein neues Image
- der Helper laesst Qdrant, SearXNG, Valkey und bestehende Volumes bewusst unangetastet
- bei Managed Installs aktualisiert der Helper die Stack-Hilfsdateien aus dem Ziel-Image, bevor nur der `aria` Service neu erstellt wird
- vor dem Recreate prueft der Helper den geplanten Host-Port; wenn der Port von einem anderen Prozess oder Container belegt ist, bricht das Update vor Veraenderungen am laufenden Service ab
- fuer `aria:alpha-local` laedt er das neueste interne TAR; fuer Registry-Stacks nutzt er `docker compose pull aria`
- wenn ein Portainer-Stack seine Compose-Datei nicht hostseitig freigibt, kann der Helper optional ueber `PORTAINER_URL` und `PORTAINER_API_KEY` direkt mit der Portainer-API reden

## Schnelle Checks

- `aria --version` zeigt die lokal installierte ARIA-Release-Kennung
- `aria version-check` vergleicht die installierte Version mit dem neuesten oeffentlichen Release
- nach staerkeren UI-/CSS-Updates kann ein harter Browser-Reload sinnvoll sein

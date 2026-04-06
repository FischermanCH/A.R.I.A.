# ARIA — Portainer Deploy Checkliste

Stand: 2026-04-02

Ziel:
- eine eigene ARIA auf einem separaten Host per Portainer Stack starten
- mit persistenten Daten
- mit Qdrant als zweitem Container
- mit möglichst wenig manuellem Gefrickel

Wichtig:
- Diese Checkliste ist für den aktuellen `ALPHA`-Stand gedacht
- ARIA ist dabei noch **kein Multi-User-System**
- empfohlen ist ein Betrieb im:
  - LAN
  - VPN
  - Home-Lab
- nicht als offen ins Internet gestellter Dienst

## 1. Voraussetzungen auf dem Zielhost

- Docker läuft
- Portainer läuft
- der Host kann:
  - `qdrant/qdrant:latest` ziehen
  - das lokale ARIA-Image per `docker load` importieren
- das LLM-/Embedding-Ziel ist vom Host bzw. Container aus erreichbar

## 2. Dateien, die du auf den Zielhost mitnimmst

Für den aktuellen lokalen ALPHA-Weg brauchst du diese zwei Dateien:

- `dist/aria-alpha-local.tar`
- `docker/portainer-stack.local.yml`

Optional zur Referenz:

- `README.md`
- `docs/setup/portainer-deploy-checklist.md`

## 3. Lokales ARIA-Image auf dem Zielhost importieren

Auf dem Zielhost:

```bash
docker load -i /pfad/zu/aria-alpha-local.tar
```

Danach kurz prüfen:

```bash
docker images | grep aria
```

Erwartung:

- ein Image `aria:alpha-local` ist vorhanden

## 4. Welche Stack-Datei du jetzt verwenden sollst

Für **den aktuellen Import-Fall mit TAR-Datei**:

- `docker/portainer-stack.local.yml`

Für **einen späteren Registry-/Docker-Hub-/GHCR-Fall**:

- `docker/portainer-stack.example.yml`

Warum zwei Dateien:

- `portainer-stack.local.yml` nutzt direkt das lokal importierte Image:
  - `aria:alpha-local`
- `portainer-stack.example.yml` ist für später gedacht, wenn das Image veröffentlicht ist

## 5. Vor dem Stack in Portainer klären

Du brauchst mindestens diese Werte:

- `ARIA_QDRANT_API_KEY`

Optional:

- `ARIA_HTTP_PORT`

Wichtig:

- `LLM` und `Embeddings` werden im aktuellen ALPHA-Weg bewusst erst nach dem ersten Login in der ARIA-Oberfläche konfiguriert
- der Stack muss dafür nicht schon vorab eine LLM-URL mitbringen

Empfehlung:

- `ARIA_QDRANT_API_KEY` als langen zufälligen Wert setzen
- denselben Wert für `aria` und `qdrant` verwenden

## 6. In Portainer setzen

### Stack-Datei

- Inhalt von `docker/portainer-stack.local.yml`

### Environment-Variablen

Mindestens setzen:

```text
ARIA_QDRANT_API_KEY=<langer-zufälliger-key>
```

Typischer Start zusätzlich:

```text
ARIA_HTTP_PORT=8800
```

Danach in ARIA selbst als erster Schritt:

1. `LLM` konfigurieren
2. `Embeddings` konfigurieren
3. `/stats` öffnen und `Startup Preflight` prüfen

## 7. Was beim ersten Start automatisch passiert

Der aktuelle Container-Start ist dafür vorbereitet:

- leere `config`-Volumes werden automatisch mit Defaults befüllt
- leere `prompts`-Volumes werden automatisch mit Defaults befüllt
- `config.yaml` wird automatisch aus `config.example.yaml` erzeugt, falls noch nicht vorhanden
- `secrets.env` wird automatisch aus `secrets.env.example` erzeugt, falls noch nicht vorhanden

Das heißt:

- ein leerer Erststart über Portainer ist möglich
- ohne dass du manuell zuerst in das Volume schreiben musst

## 8. Erster Browser-Check

Nach dem Deploy prüfen:

1. ARIA öffnen
   - `http://<host>:<ARIA_HTTP_PORT>`

2. Qdrant optional prüfen
   - `http://<host>:6333`

3. Login-Seite muss im Bootstrap-Fall zeigen:
   - es existiert noch kein User
   - der erste User wird automatisch Admin

4. ersten User anlegen

5. danach prüfen:
   - Login klappt
   - Admin-Modus ist direkt aktiv
   - `Config` ist sichtbar

## 9. Quick Start nach dem ersten Login

Empfohlene Reihenfolge:

1. `LLM` konfigurieren
2. `Embeddings` konfigurieren
3. `/stats` öffnen
   - Preflight prüfen
4. `/memories` öffnen
5. ersten einfachen Chat-Test machen

Dann erst:

6. Connections hinzufügen
7. Guardrails setzen
8. operative Skills nutzen

## 10. Wenn etwas nicht klappt

### ARIA startet nicht

Prüfen:

- Port-Konflikt auf `8800`
- Stack-Logs in Portainer

## 11. Lokale Update-Pipe auf dem Zielhost

Wenn du auf dem Zielhost mit lokal geladenen TAR-Dateien arbeitest, kannst du den Stack fuer Updates gleich lassen.

Der empfohlene Weg:

1. neues TAR nach `/mnt/NAS/aria-images/` kopieren
2. `docker/update-local-aria.sh` auf den Zielhost legen
3. dort die lokale Stack-Datei neben die TAR-Dateien nach `/mnt/NAS/aria-images/portainer-stack.alpha3.local.yml` legen
4. optional eine Env-Datei nach `/mnt/NAS/aria-images/aria-stack.env` legen

Beispiel fuer die Env-Datei:

```text
ARIA_QDRANT_API_KEY=<dein-qdrant-key>
```

Dann auf dem Zielhost:

```bash
chmod +x /mnt/NAS/aria-images/update-local-aria.sh
/mnt/NAS/aria-images/update-local-aria.sh
```

Standardannahmen des Scripts:

- TAR-Verzeichnis: `/mnt/NAS/aria-images`
- Stack-Datei: `/mnt/NAS/aria-images/portainer-stack.alpha3.local.yml`
- Env-Datei: `/mnt/NAS/aria-images/aria-stack.env`
- Image-Name: `aria:alpha-local`

Wichtig:

- das Script erstellt nur den Service `aria` neu
- `qdrant` bleibt laufen
- die Volumes bleiben erhalten
- der Stack-Inhalt bleibt gleich

Wenn keine Env-Datei vorhanden ist, versucht das Script den aktuell laufenden Qdrant-Key aus den vorhandenen Containern zu uebernehmen.

Neu fuer den Dev-Host:

- Build-Artefakte sollten bevorzugt direkt nach `/mnt/NAS/aria-images` exportiert werden
- wenn der NAS-Mount nicht verfuegbar ist, bleibt `dist/` der lokale Fallback
- dafuer gibt es den Helper:

```bash
docker/export-local-build.sh
```

## 12. Alternative: Update per SSH-Pull vom Dev-Host

Wenn der Zielhost den Dev-Host im lokalen Netz per SSH erreichen kann, ist das oft bequemer als manuelles Kopieren.

Dann liegt auf dem Zielhost z. B. in `/mnt/NAS/aria-images`:

- `pull-from-dev.sh`
- `update-local-aria.sh`
- `portainer-stack.alpha3.local.yml`
- `aria-stack.env`

Der Ablauf:

1. auf dem Dev-Host ein neues TAR bauen
2. auf dem Zielhost `pull-from-dev.sh` starten
3. das Script holt:
   - das neueste `aria-alpha*-local.tar`
   - `portainer-stack.alpha3.local.yml`
   - `update-local-aria.sh`
   - `aria-stack.env.example`
   - optional `samples/`
4. danach startet es automatisch `update-local-aria.sh`

Wichtig:

- `aria-stack.env` bleibt lokal auf dem Zielhost
- dort bleibt dein echter `ARIA_QDRANT_API_KEY`
- Secrets werden nicht vom Dev-Host uebernommen

Beispiel auf dem Zielhost:

```bash
cd /mnt/NAS/aria-images
chmod +x pull-from-dev.sh
DEV_SSH=<dev-user>@<dev-host> ./pull-from-dev.sh
```

Wichtige Standardwerte des Scripts:

- Remote-Basis: `/home/aria/ARIA`
- Lokal: `/mnt/NAS/aria-images`

Bei Bedarf ueberschreibbar:

```bash
DEV_SSH=<dev-user>@<dev-host> \
REMOTE_BASE_DIR=/home/aria/ARIA \
LOCAL_DIR=/mnt/NAS/aria-images \
./pull-from-dev.sh
```
- `ARIA_QDRANT_API_KEY` gesetzt?
- wurde das Image wirklich importiert?
  - `docker images | grep aria`

### Qdrant ok, aber LLM nicht

Prüfen:

- wurde `LLM` in ARIA bereits konfiguriert?
- wurde `Embeddings` in ARIA bereits konfiguriert?
- ist die eingetragene LiteLLM-URL vom ARIA-Container aus erreichbar?

### Login da, aber Chat antwortet nicht sinnvoll

Prüfen:

- LLM-Config
- Embeddings-Config
- `/stats` -> `Startup Preflight`

## 11. Für spätere Updates

Der geplante Weg bleibt:

1. Änderungen in `dev`
2. neues Image bauen
3. neues TAR exportieren oder später in Registry pushen
4. auf dem Zielhost neues Image laden / ziehen
5. Stack neu deployen
6. Daten und Konfiguration bleiben in den Volumes erhalten

Portainer passt dafür gut, weil:

- Volumes erhalten bleiben
- Stack-Variablen erhalten bleiben
- Image-Wechsel klar kontrollierbar ist

## 12. Minimaler Zielzustand

Damit die eigene ARIA auf dem fremden Host als “einsatzbereit” gilt:

- Stack läuft stabil
- erster User wurde erfolgreich angelegt
- Admin-Modus aktiv
- LLM erreichbar
- Qdrant erreichbar
- `/health` ok
- `/stats` Preflight ohne grobe Fehler

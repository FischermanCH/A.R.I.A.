# ARIA - Versioning / Git Release Notes Plan

Stand: 2026-04-03

Zweck:
- saubere technische Versionierungs- und Release-Notes-Struktur für GitHub
- Bugfixes und neue Features pro Release nachvollziehbar trennen
- Current-ALPHA-Flow in ein später public-taugliches Git-/Docker-Release-Modell überführen

## Aktueller Zustand

- Python-Projektversion in `pyproject.toml`:
  - `0.1.0`
- ARIA Release Label in der UI aktuell:
  - `0.1.0-alpha21`
- interne Build-Artefakte aktuell:
  - bevorzugt: `/mnt/NAS/aria-images/aria-alphaN-local.tar`
  - Fallback lokal: `dist/aria-alphaN-local.tar`
- Änderungslog aktuell:
  - `project.docu/alpha-build-log.md`

## Empfohlene Release-Tag-Strategie

### Pre-Releases

Git-Tags:
- `v0.1.0-alpha.21`
- `v0.1.0-alpha.22`
- ...

Docker-Tags:
- `aria:0.1.0-alpha.21`
- optional zusätzlich:
  - `aria:alpha`

### Beta

Git-Tags:
- `v0.2.0-beta.1`
- `v0.2.0-beta.2`

Docker-Tags:
- `aria:0.2.0-beta.1`
- optional zusätzlich:
  - `aria:beta`

### Stable

Git-Tags:
- `v1.0.0`
- `v1.0.1`

Docker-Tags:
- `aria:1.0.0`
- optional zusätzlich:
  - `aria:latest`

## Empfohlenes Changelog-Format

Eine root-nahe `CHANGELOG.md` mit pro Release:

```markdown
## [0.1.0-alpha.21] - 2026-04-03

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Security
- ...

### Known Limitations
- ...

### Upgrade Notes
- ...
```

## Mapping von aktuellem Alpha-Build-Log auf Git-Releases

`project.docu/alpha-build-log.md` bleibt als interne Detail-Historie nützlich.

Für Public GitHub Releases sollte daraus je Release eine kompakte Release Note entstehen:

- **Added**
  - neue Features, neue Connection-Typen, neue UI-Flows, neue Themes, neue Samples
- **Changed**
  - UX-/Routing-/Architektur-Änderungen ohne Bugcharakter
- **Fixed**
  - konkrete Bugs, falsche Redirects, kaputte Uploads, falsches Routing, defekte Statusanzeigen
- **Security**
  - Guardrail-/Auth-/Secret-/Sanitizing-Änderungen
- **Known Limitations**
  - ALPHA-Grenzen und bekannte offene Produktentscheidungen
- **Upgrade Notes**
  - was User beim Update beachten müssen
  - ob neue ENV-/Config-Keys nötig sind
  - ob harte Browser-Reloads bei UI-/CSS-Änderungen sinnvoll sind

## Empfohlener technischer Release-Ablauf

### 1. Versionsstand festlegen

- entscheiden, ob nächster Release:
  - `alpha.N`
  - `beta.N`
  - oder stabiler SemVer-Tag
- `pyproject.toml` Version prüfen
- UI Release-Label aktualisieren
- Release-Notes-Abschnitt in `CHANGELOG.md` ergänzen

### 2. Tests

- kompletter `pytest` Lauf
- ggf. Smoke-Test lokal:
  - Chat
  - Login
  - `/health`
  - `Statistiken`
  - Skill Import
  - eine SSH- oder RSS-Connection

### 3. Docker Image bauen

- Image mit **versioniertem Tag** bauen
- optional zusätzlich Alias-Tag (`alpha`, `beta`, `latest`) setzen
- Release Label im Container prüfen
- `ssh-keygen` und zentrale Runtime-Tools im Image prüfen

### 4. Upgrade-Test

- bestehende Container-Instanz mit persistenten Volumes aktualisieren
- prüfen, dass erhalten bleiben:
  - Config
  - Secrets
  - Connections
  - Skills
  - Memories
  - Logs/Stats

### 5. Git Release

- Commit mit Feature-/Fix-Doku
- Git-Tag setzen, z. B.:
  - `git tag -a v0.1.0-alpha.21 -m "ARIA 0.1.0-alpha.21"`
- Tag pushen
- GitHub Release Notes aus `CHANGELOG.md` übernehmen

### 6. Registry Publish

- Docker-Image mit Versionstag pushen
- optional Alias-Tag aktualisieren
- Stack-/Compose-Beispiele prüfen, ob der Image-Tag konsistent ist

## Empfohlene Git-Commit-Konvention

Für saubere spätere Release Notes reicht ein leichtgewichtiges Schema:

- `feat: ...`
- `fix: ...`
- `ui: ...`
- `docs: ...`
- `refactor: ...`
- `test: ...`
- `chore: ...`

Beispiele:
- `feat(rss): add OPML import/export`
- `fix(skills): prevent generic discord capability from bypassing custom skill`
- `ui(stats): replace OK labels with status lamps`
- `docs(release): add public release architecture summary`

## Konkrete nächste Umsetzungsschritte im Repo

1. root-`CHANGELOG.md` anlegen
2. `README.md` später auf die neuen Release-Doku-Dateien verlinken
3. Build-/Release-Flow von `alpha-build-log.md` schrittweise in `CHANGELOG.md` überführen
4. Docker Build-Scripts/Stack-Beispiele später auf versionierte Registry-Tags statt nur `aria:alpha-local` vorbereiten
5. vor Public Release finale Entscheidung:
   - `alpha` weiterführen
   - oder erster externer `beta`-Tag

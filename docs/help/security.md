# ARIA Hilfe: Security und Secrets

Stand: 2026-03-26

## Zweck

Dieses Dokument beschreibt, wie ARIA sensible Werte (API-Keys, Tokens, Credentials) sicher speichert und wie die Security-Tools genutzt werden.

## Was wird verschlüsselt gespeichert

In der Secure-DB (`data/auth/aria_secure.sqlite`) liegen aktuell:

- `llm.api_key`
- `embeddings.api_key`
- `channels.api.auth_token`
- Profil-API-Keys:
  - `profiles.llm.<name>.api_key`
  - `profiles.embeddings.<name>.api_key`
- Benutzer-Credentials (User + Passwort-Hash + Rolle)

Hinweis:

- Passwörter werden nicht im Klartext gespeichert (Argon2-Hash).
- Secrets werden AES-256-GCM verschlüsselt gespeichert.

## Wo liegt der Schluessel

Der Master-Key liegt in:

`config/secrets.env`

Variable:

`ARIA_MASTER_KEY`

Weitere Runtime-Secrets:

- `ARIA_AUTH_SIGNING_SECRET`
- `ARIA_FORGET_SIGNING_SECRET`

Hinweis:

- Diese beiden Signatur-Secrets dürfen ebenfalls nicht im Code oder in Git landen.
- Wenn sie nicht per Umgebung gesetzt sind, erzeugt ARIA beim ersten Start persistente Werte in `config/secrets.env`.
- Die Auflösung erfolgt zentral über [`aria/core/config.py`](https://github.com/FischermanCH/A.R.I.A./blob/main/aria/core/config.py) (keine direkten `os.environ`-Zugriffe in App-/Admin-Modulen).

Dateirechte:

- empfohlen und umgesetzt: `600`

## Migration von Klartext nach Secure-DB

Befehl:

`./aria.sh secure-migrate`

Was passiert:

1. Master-Key wird erzeugt, falls noch nicht vorhanden.
2. Secrets aus `config/config.yaml` werden in die Secure-DB übernommen.
3. API-Key-Felder werden in `config.yaml` geleert.
4. Backup wird erstellt: `config/config.yaml.bak.<timestamp>`

## Git- und Container-Ready

Für einen sauberen Public-Repo-/Container-Workflow bleiben folgende Dateien lokal:

- `config/config.yaml`
- `config/secrets.env`
- `data/auth/`
- `data/logs/`
- `data/skills/`

Im Repo bleiben nur Beispiel-/Vorlage-Dateien:

- [`config/config.example.yaml`](https://github.com/FischermanCH/A.R.I.A./blob/main/config/config.example.yaml)
- [`config/secrets.env.example`](https://github.com/FischermanCH/A.R.I.A./blob/main/config/secrets.env.example)

Ziel:

- keine Credentials im Code
- keine Secrets in Git
- alle ENV-/Secret-Zugriffe zentral in [`aria/core/config.py`](https://github.com/FischermanCH/A.R.I.A./blob/main/aria/core/config.py)

## Container-Hinweis

Der Docker-Startpfad lädt `config/secrets.env` beim Container-Start und startet danach `uvicorn`.

Relevant:

- [`Dockerfile`](https://github.com/FischermanCH/A.R.I.A./blob/main/Dockerfile)
- [`docker/entrypoint.sh`](https://github.com/FischermanCH/A.R.I.A./blob/main/docker/entrypoint.sh)
- `docker-compose.yml` (lokaler Repo-/Build-Stack)
- `docker-compose.public.yml` (Public-/Registry-Stack mit `qdrant`, `searxng` und `searxng-valkey`)

Dadurch bleiben Secrets auch im Container ausserhalb des Images und können per Volume oder Deployment-Secret bereitgestellt werden.

## User-Verwaltung (CLI)

Benutzer anzeigen:

`./aria.sh user-admin list`

Benutzer anlegen/aktualisieren:

`./aria.sh user-admin add <username> --role user`

Danach wird ein Passwort interaktiv abgefragt und gehasht gespeichert.
Passwort-Mindestlaenge: 8 Zeichen.

## User-Verwaltung (UI)

- Seite: `/config/users` (nur Admin)
- Möglich:
  - User anlegen
  - Rolle/Aktiv-Status ändern
  - Passwort setzen
  - Username umbenennen (case-sensitive)
- Schutz:
  - Ziel-Username darf nicht bereits existieren
  - letzter aktiver Admin bleibt geschuetzt
  - eigener Admin kann sich nicht selbst deaktivieren/degradieren

## Login im Web-UI

- URL: `/login`
- Session-Cookie: signiert (`aria_auth_session`), gültig für 12h
- Bootstrap:
  - Wenn noch kein Benutzer existiert, wird der erste Login nur dann als `admin` angelegt, wenn `security.bootstrap_locked: false`
  - Bei `security.bootstrap_locked: true` ist kein Auto-Bootstrap erlaubt
- Rollen:
  - `admin`: Zugriff auf `Config`
  - `user`: Chat, Memories, Stats
- Username-Regel:
  - Benutzernamen sind case-sensitive.
  - Beispiel: `alice` und `Alice` sind zwei verschiedene Konten.

Hinweis:

- Ohne Login gibt es Redirect auf `/login`.
- Bei abgelaufener/ungültiger Session gibt es Redirect auf `/session-expired` und danach zum Login.
- Login-Cookie wird bei jedem Request gegen den aktiven User-Status im Security-Store geprüft.
  - User deaktiviert/entfernt -> Session wird sofort ungültig
- `Config` ist im Header nur für `admin` sichtbar.
- User-Verwaltung im UI unter: `Config > Team & Zugriff` (`/config/users`)

## Security-Konfiguration

In `config/config.yaml`:

```yaml
security:
  enabled: true
  db_path: "data/auth/aria_secure.sqlite"
  bootstrap_locked: true
```

Im Admin-UI:

- Seite: `/config/security`
- Dort kann `bootstrap_locked` direkt geschaltet und gespeichert werden.

Wichtig:

- Wenn `security.enabled: false`, werden keine Secrets aus der Secure-DB in die Runtime geladen.
- Bei aktiviertem Security-Modus sollten API-Key-Felder im YAML leer bleiben.

## Security Header (Default)

ARIA setzt für Web-Responses standardmaessig:

- `Content-Security-Policy`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy`
- `Permissions-Policy`

## CSRF-Schutz

ARIA schuetzt zustandsändernde Browser-Requests (`POST/PUT/PATCH/DELETE`) mit CSRF-Token:

- Token als Cookie: `aria_csrf_token`
- Token wird automatisch in Formulare eingefuegt
- Token wird bei HTMX/FETCH als Header `X-CSRF-Token` gesendet
- Server validiert Token gegen Cookie (Double-Submit-Pattern)

Bei fehlendem/ungültigem Token wird der Request mit `403` abgelehnt.

## Troubleshooting

- Fehler: "ARIA_MASTER_KEY fehlt."
  - `config/secrets.env` prüfen
  - ARIA über `./aria.sh start` starten (lädt `secrets.env`)
- Neue Keys in UI gespeichert, aber nicht wirksam:
  - `security.enabled` prüfen
  - ARIA neu starten: `./aria.sh restart`
  - DB-Pfad prüfen: `security.db_path`

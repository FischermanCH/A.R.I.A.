# ARIA - Setup / Quick Overview

Stand: 2026-04-07

Zweck:
- technische Kurz-Erklärung, **wie ARIA grundsätzlich aufgesetzt und betrieben wird**
- dient als Rohmaterial für spätere Quickstart-/Setup-Texte im README, Release-Text oder Wiki

## Betriebsmodell

ARIA kann lokal direkt aus dem Repo oder als Docker-/Portainer-Stack betrieben werden.

Empfohlener ALPHA-Betrieb:
- separater Docker-Host oder Homelab-Server
- Zugriff nur im LAN oder via VPN
- persistente Volumes für Config, Prompts, Data
- Qdrant als eigener Service/Container
- optional SearXNG als eigener Search-Service/Container fuer Websuche
- bei SearXNG bevorzugt eine statische `searxng.settings.yml` statt Shell-Logik im Stack

Nicht empfohlen im aktuellen ALPHA-Stand:
- offener Public-Internet-Betrieb ohne vorgeschaltete Schutzschicht
- produktive Multi-User-Team-Setups mit echten Sharing-/RBAC-Anforderungen

## Setup-Pfade

### 1. Lokaler Repo-Start

Technischer Ablauf:
1. Repo klonen
2. Python-Dependencies installieren
3. `config/config.example.yaml` nach `config/config.yaml` kopieren
4. `config/secrets.env.example` nach `config/secrets.env` kopieren
5. ARIA mit `./aria.sh start` starten
6. Browser öffnen und ersten Benutzer anlegen

Zentrale Dateien:
- `pyproject.toml`
- `aria.sh`
- `config/config.example.yaml`
- `config/secrets.env.example`

### 2. Docker Compose

Technischer Ablauf:
1. Repo auf den Zielhost legen
2. `.env.example` nach `.env` kopieren
3. `.env` setzen, mindestens Qdrant API Key + SearXNG Secret
4. `docker compose -f docker-compose.public.yml up -d`
5. optional SearXNG im selben Stack mitstarten
6. ARIA im Browser öffnen und initialen Admin-User erstellen

Zentrale Dateien:
- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.public.yml`
- `docker/searxng.settings.yml`
- `.env.example`
- `docker/entrypoint.sh`

### 3. Portainer Stack

Technischer Ablauf:
1. Portainer-Stack-YAML als Vorlage nehmen
2. persistente Named Volumes für `config`, `prompts`, `data`, `qdrant_storage`
3. optional zusaetzlich SearXNG/Valkey im selben Stack mitnehmen
4. Environment-Werte setzen, mindestens `ARIA_QDRANT_API_KEY`
5. Stack starten
6. ARIA im Browser öffnen und Erstnutzer/LLM/Connections konfigurieren

Zentrale Dateien:
- `docker/portainer-stack.public.yml`
- `docker/portainer-stack.example.yml`
- `docker/portainer-stack.alpha3.local.yml`
- `docker/aria-stack.env.example`
- `docker/searxng.settings.yml`

## First-Run Flow

Beim ersten Start:
1. erster User wird im Browser angelegt
2. dieser erste User wird Admin
3. Admin-Modus ist aktiv
4. danach LLM/Embeddings konfigurieren
5. danach Connections und Skills anlegen/importieren

## Persistenz / Volumes

Für Containerbetrieb sind diese Mounts/Volumes wichtig:
- `/app/config`
- `/app/prompts`
- `/app/data`
- Qdrant Storage Volume für den Qdrant-Container
- optional SearXNG Cache-Volume fuer den Search-Container
- bei SearXNG zusaetzlich eine gemountete `settings.yml` nach `/etc/searxng/settings.yml`

Wichtiges Verhalten:
- wenn `config` oder `prompts` beim ersten Containerstart leer sind, füllt der EntryPoint sie aus den eingebauten Defaults
- Runtime-Daten, Skills, Logs, Chat-History und Memories bleiben im `data`-Volume
- Updates sollen Container/Image ersetzen, aber Volumes behalten

## Zentrale Runtime-Konfiguration

ARIA liest primär:
- `config/config.yaml`
- `config/secrets.env`

ENV-Overrides laufen über `ARIA_*`.

Wichtige Beispiele:
- `ARIA_ARIA_HOST`
- `ARIA_ARIA_PORT`
- `ARIA_PUBLIC_URL`
- `ARIA_QDRANT_API_KEY`
- `SEARXNG_SECRET`

Wenn SearXNG im Stack mitlaeuft, nutzt ARIA intern standardmaessig diese feste Stack-URL:
- `http://searxng:8080`

Auf der SearXNG-Connection-Seite pflegst du pro Profil dann nur noch Suchverhalten und Routing-Metadaten.

Fuer den SearXNG-Container selbst sind typischerweise gesetzt:
- `SEARXNG_SECRET`
- `SEARXNG_LIMITER=false`
- `SEARXNG_VALKEY_URL`

## LLM / Embeddings

ARIA spricht LLMs über LiteLLM/OpenAI-kompatible Konfigurationen an.

Typische Setup-Variante:
- lokal/Ollama für private Modelle
- OpenAI/OpenRouter/Anthropic-kompatible Endpoints für Remote-Modelle
- Embeddings separat konfiguriert

Relevante Config-Bereiche:
- `llm`
- `embeddings`
- `pricing`

## Security-Basics

- erster User = Bootstrap-Admin
- Admin-Modus für System-/Connection-/Skill-Konfiguration
- Secrets in lokalem Secure Store
- Qdrant API Key explizit setzen
- LAN/VPN-Betrieb bevorzugen

## Update-Strategie

Aktuell bewährter interner Update-Pfad:
- auf `dev` fixen
- neues `aria-alphaN-local.tar` bauen
- auf dem Zielhost per `aria-pull` aktualisieren
- nur ARIA-Container neu erstellen, Qdrant und Volumes bleiben erhalten

Für Public Release später:
- versionierte Git-Tags
- versionierte Docker-Image-Tags
- Release Notes + Upgrade Notes pro Version

# ARIA - Third-Party Notices

Stand: 2026-04-08

ARIA selbst steht unter der MIT License, siehe `LICENSE`.

ARIA baut bewusst auf mehreren starken Open-Source-Projekten und externen Runtime-Komponenten auf. Diese Datei ist eine kurze, faire Würdigung und ein technischer Hinweis, damit klar bleibt, was ARIA selbst ist und welche Projekte als Grundlage oder Integration dazugehören.

## Besonders wichtig

### Qdrant

Qdrant ist der Vector Store, auf dem ARIAs semantische Memory-Schicht aufbaut.

- Projekt: https://qdrant.tech/
- Repository: https://github.com/qdrant/qdrant
- Python Client: https://github.com/qdrant/qdrant-client

ARIA betreibt Qdrant typischerweise als separaten Container im selben Compose-/Portainer-Stack. Qdrant ist kein ARIA-eigener Codebestand, sondern ein eigenständiges Upstream-Projekt, das hier mit Respekt und Dankbarkeit genutzt wird.

### SearXNG

SearXNG ist der self-hosted Meta-Search-Dienst hinter ARIAs pre-alpha Websuche.

- Projekt: https://docs.searxng.org/
- Repository: https://github.com/searxng/searxng
- Lizenz: AGPL-3.0

ARIA nutzt SearXNG bewusst als separaten, unveränderten Stack-Dienst und spricht nur die JSON-Search-API an. SearXNG ist kein in ARIA eingebetteter Codepfad, sondern ein eigenständiges Upstream-Projekt mit eigener Lizenz und eigenem Runtime-Verhalten. Diese Trennung ist technisch und lizenzseitig bewusst so gewählt.

### Valkey

Valkey wird im ARIA-Stack als separater Hilfsdienst für den SearXNG-Container eingesetzt.

- Projekt: https://valkey.io/
- Repository: https://github.com/valkey-io/valkey
- Lizenz: BSD-3-Clause

Valkey ist ebenfalls kein ARIA-eigener Codebestand, sondern ein eigenständiges Upstream-Projekt, das im Stack als Cache-/Runtime-Komponente mitläuft.

## Wichtige Python-/Runtime-Abhängigkeiten

ARIA nutzt unter anderem:

- FastAPI - Web/API Framework
- Uvicorn - ASGI Server
- Jinja2 - Server-side Templates
- LiteLLM - Provider-Abstraktion für LLM-Backends
- qdrant-client - Qdrant-Anbindung
- pypdf - PDF-Text-Extraktion für RAG-Uploads
- Pydantic / pydantic-settings - Config- und Datenmodelle
- PyYAML - YAML-Konfiguration
- Paramiko - SSH
- pysmb - SMB
- paho-mqtt - MQTT
- cryptography - kryptografische Basisfunktionen
- argon2-cffi - Passwort-Hashing
- python-multipart - Form-/Upload-Verarbeitung
- NumPy - numerische Hilfsfunktionen
- htmx - kleines Frontend-Interaktions-Toolkit ohne SPA-Buildchain

## Lizenzhinweis zu Drittprojekten

Die oben genannten Drittprojekte stehen jeweils unter ihren eigenen Upstream-Lizenzen. Diese Datei ersetzt **nicht** deren Original-Lizenztexte.

Vor einem Public Release sollten die final ausgelieferten Container- und Paketabhängigkeiten noch einmal gegen deren Upstream-Lizenzen geprüft und bei Bedarf um zusätzliche NOTICE-/Attribution-Texte ergänzt werden.

## Design-Prinzip

ARIA versucht nicht, Qdrant, SearXNG, Valkey, LiteLLM, FastAPI oder andere Upstream-Projekte als eigene Arbeit darzustellen. ARIA ist die Integrations-, UI-, Routing-, Skill- und Memory-Orchestrierungsschicht darüber; die zugrundeliegenden Infrastruktur- und Framework-Projekte verdienen explizite Nennung.

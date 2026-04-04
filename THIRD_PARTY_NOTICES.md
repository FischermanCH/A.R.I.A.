# ARIA - Third-Party Notices

Stand: 2026-04-03

ARIA selbst steht unter der MIT License, siehe `LICENSE`.

ARIA baut bewusst auf mehreren starken Open-Source-Projekten und externen Runtime-Komponenten auf. Diese Datei ist eine kurze, faire Würdigung und ein technischer Hinweis, damit klar bleibt, was ARIA selbst ist und welche Projekte als Grundlage oder Integration dazugehören.

## Besonders wichtig

### Qdrant

Qdrant ist der Vector Store, auf dem ARIAs semantische Memory-Schicht aufbaut.

- Projekt: https://qdrant.tech/
- Repository: https://github.com/qdrant/qdrant
- Python Client: https://github.com/qdrant/qdrant-client

ARIA betreibt Qdrant typischerweise als separaten Container im selben Compose-/Portainer-Stack. Qdrant ist kein ARIA-eigener Codebestand, sondern ein eigenständiges Upstream-Projekt, das hier mit Respekt und Dankbarkeit genutzt wird.

## Wichtige Python-/Runtime-Abhängigkeiten

ARIA nutzt unter anderem:

- FastAPI - Web/API Framework
- Uvicorn - ASGI Server
- Jinja2 - Server-side Templates
- LiteLLM - Provider-Abstraktion für LLM-Backends
- qdrant-client - Qdrant-Anbindung
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

ARIA versucht nicht, Qdrant, LiteLLM, FastAPI oder andere Upstream-Projekte als eigene Arbeit darzustellen. ARIA ist die Integrations-, UI-, Routing-, Skill- und Memory-Orchestrierungsschicht darüber; die zugrundeliegenden Infrastruktur- und Framework-Projekte verdienen explizite Nennung.

# ARIA - Hilfe-System / Doku-Hub

Stand: 2026-05-12

## Aktuelle Richtung

`/help` ist der lokale Docs-Hub von ARIA. Die Inhalte sollen dieselben Kerninformationen liefern wie das GitHub-Wiki, damit Nutzer nicht zwischen altem Wiki-Stand und neuer Produktrealitaet hin und her fallen.

Seit `0.1.0-alpha251` muessen Hilfe und Wiki klar abbilden:

- recipe-first statt Skill-first
- Agentic Action Flow: Kontext anreichern, LLM-Draft, Policy/Guardrail, Runtime
- Token-/Kosten-Sichtbarkeit fuer sichtbare und interne LLM-Aufrufe
- LiteLLM-GitHub-Preisliste als Pricing-Quelle ohne LiteLLM-Paket
- One-Click-Bestaetigungen im Chat
- Multi-Target-Read-only-Checks, z. B. SSH-Fleet-Disk-Checks
- RSS-Digests mit Quellen und Links
- sicherer Managed-Update-Pfad

## Was `/help` heute sein soll

`/help` ist ein praktischer Einstieg fuer:

- Quick Start
- Memory und Dokumenten-RAG
- Rezepte
- Connections
- Releases und Upgrades
- Pricing
- Qdrant
- SearXNG
- Security und Guardrails

Quellen liegen in:

- `docs/wiki/`
- `docs/help/`

Lokalisierte Varianten verwenden `.de.md` und `.en.md`, wo sinnvoll.

## Was bewusst nicht Prioritaet hat

Nicht der aktuelle Fokus:

- Info-Icons an jedem einzelnen Formularfeld
- Popover pro UI-Feld
- separate Doku-Engine
- KI-generierte Live-Hilfe ohne Review

Sinnvoll bleiben kurze Kontext-Boxen mit Link auf `/help`, besonders bei LLM, Embeddings, Memory, RSS, Pricing und Security.

## Pflege-Regeln

- Neue Nutzerbegriffe muessen recipe-first sein.
- Legacy-`Skill` nur noch als Kompatibilitaet erwaehnen.
- Public-Release-Stand und Update-Pfad muessen in Help/Wiki/README zusammenpassen.
- Security-/Pricing-Texte duerfen keine harten Versprechen machen, die die Alpha nicht halten kann.
- Wenn eine Hilfe-Seite lokal aktualisiert wird, das GitHub-Wiki im gleichen Schritt mitziehen.

## Zentrale Help-Themen

### Agentic Action Flow

ARIA soll bei Aktionsprompts nicht nur deterministisch raten. Der erwartete Ablauf ist:

1. Prompt erkennen und mit Kontext anreichern
2. Connections, Rezepte, Qdrant-Kandidaten und Experience Memory sammeln
3. LLM einen begrenzten Draft bauen lassen, wenn noetig
4. Guardrails/Policy entscheiden lassen
5. Runtime ausfuehren oder sicher blocken/fragen

### Kosten / Pricing

Kosten werden zentral gemessen. Wenn ein LLM-Aufruf fuer Routing oder Guardrails stattfindet, muss er in Chat-Details und `/stats` sichtbar sein.

### Updates

Managed Updates duerfen Qdrant, SearXNG, Valkey und Volumes nicht unnoetig recreaten. Der Host-Update-Helper prueft Portkonflikte vor dem ARIA-Recreate.

## Umsetzung

Die aktuelle Hilfe wird direkt aus Markdown gerendert. Der Help-Katalog steht in `aria/main.py`. Die Render-Route liegt in `aria/web/docs_surface_routes.py`.

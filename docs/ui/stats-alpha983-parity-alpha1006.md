# Statistik-Parität Alpha983 → Alpha1005

Funktionale Referenz ist `v0.1.0-alpha.983`. Alpha1005 übernimmt deren konkrete Prüfungen und Modellrollen in das neue Owner-Layout. Der Seitenaufruf bleibt passiv: Er liest lokale Konfiguration, Logs und gespeicherte Zustände, startet aber keine Provider-, Verbindungs-, MCP- oder Preislisten-Abfrage.

## Übernommene Prüfungen

| Alpha983 | Alpha1005 |
|---|---|
| Prompt-Dateien, Qdrant, Chat-LLM, Embeddings; Startzeit im Blockkopf | Startprüfung |
| ARIA-Laufzeit, Modell-Stack, eine live geladene Qdrant-Prüfung, Sicherheitsspeicher, Aktivitäten/Logs, Verbindungen, MCP-Server | Laufzeit & Dienste |
| Release, Modul-Registry, Modell-Gateway/Usage-Meter, Preisabdeckung, Kostenerfassung, Rezept-Gedächtnis, Update-Pfad | Betrieb & Release |
| Chat-Modell, Embedding-Modell, Web-/Suchmodell, API-Basis je Rolle, gemeinsamer/getrennter Gateway, Usage-Meter, Token-Protokoll, Web-LLM-Anfragen, native Suche und deren Kosten | eingeklappter Technik-Bereich |

Jede Prüfung hat eine grüne, gelbe oder rote Ampel. Gelbe und rote Befunde nennen das konkrete Problem und verlinken die passende Verwaltungsseite. Blockköpfe zeigen die drei Statuszähler wie in Alpha983.

## Bewusst entfernt

| Element aus Alpha983 | Begründung |
|---|---|
| Eigene Kachel „Startzeit“ | Die lokale Startzeit steht im Kopf von „Startprüfung“ und ist kein eigenständiger Gesundheitscheck. |
| Meta-Kacheln „Startprüfung“ und „Laufzeit-Zustand“ | Sie wiederholten nur die Zähler ihrer jeweiligen Blöcke, ohne ein konkretes Problem zu benennen. |
| Zweite Qdrant-Kachel und „Zusatzdienste“ | Beide wiederholten ausschließlich Qdrant; Alpha1007 hat neben der Startkachel genau eine live geladene Qdrant-Kachel. |
| Live-Aufruf des Update-Helpers beim Öffnen von `/stats` | Der Owner-Status verwendet den gespeicherten Update-Zustand und verlinkt `/updates`; ein GET auf `/stats` darf kein Netz auslösen. |
| Live-Prüfung jeder Connection beim Öffnen von `/stats` | Gespeicherte Einzelzustände bleiben sichtbar und verlinkt; echte Verbindungsprüfungen erfolgen ausschließlich über die jeweilige Connection-Seite. |
| Eigenständige Routing-Index-Live-Prüfung | Modul-Registry und gespeicherter Laufzeitzustand decken die passive Owner-Sicht ab; der Qdrant-/Routing-Test bleibt an seiner autorisierten Diagnoseoberfläche. |
| Eigenständige Recipe-Experience-Qdrant-Abfrage | „Rezept-Gedächtnis“ bleibt als Prüfung erhalten, nutzt aber den gespeicherten Qdrant-Zustand statt beim Seitenaufruf eine neue Abfrage zu starten. |

Diese Entfernungsliste ist absichtlich eng: Sie entfernt nur aktive Probe-Nebenwirkungen, nicht die dazugehörige Owner-Information.

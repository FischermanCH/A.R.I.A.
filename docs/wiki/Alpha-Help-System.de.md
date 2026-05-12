# ARIA Alpha Hilfe

Stand: 2026-05-12 / Public Alpha `0.1.0-alpha251`

Diese Seite ist die praktische Kurz-Hilfe fuer ARIA Alpha. Sie beschreibt den aktuellen Stand nach dem grossen Umbau von Legacy-Skills zu Rezepten, LLM-gestuetzter Action-Planung und kontrollierter Ausfuehrung.

## Was ARIA Alpha gerade ist

ARIA ist ein persoenlicher, selbst gehosteter AI-Assistent fuer LAN, VPN und Homelab.

Gut geeignet fuer:

- einen eigenen AI-Workspace im Browser
- Memory und Dokumenten-RAG mit Qdrant
- Notizen als Markdown-Arbeitsbereich
- sichere Connections zu SSH, SFTP, SMB, RSS, Discord, HTTP API, Webhook, Mail, MQTT, SearXNG und Google Calendar
- recipe-first Automationen mit Guardrails
- LLM-gestuetzte Action-Drafts: ARIA versteht natuerliche Prompts, schlaegt konkrete Aktionen vor und laesst Policy/Guardrails entscheiden

Noch nicht Ziel der Alpha:

- direkter Public-Internet-Betrieb ohne Reverse-Proxy-/Auth-Konzept
- vollstaendiges Multi-User-/RBAC-Modell
- Enterprise-Betrieb ohne technische Betreuung

## Erster Start

Beim ersten Start legst du den ersten Benutzer an. Dieser Benutzer wird automatisch Admin.

Danach zuerst pruefen:

1. `/config/llm` - Chat-Modell und API-Zugang
2. `/config/embeddings` - Embedding-Modell fuer Memory und Routing
3. `/stats` - Preflight, Qdrant, Modellstatus, Token/Kosten und Pricing Coverage
4. `/connections/types` - Connections zu deinen Systemen
5. `/recipes` - Rezepte importieren, reviewen oder mit dem Wizard bauen
6. `/config/routing` und `/config/workbench/routing` - Routing-Dry-runs und Debug-Prompts, wenn ARIA ein Ziel falsch versteht

## Admin-Modus und User-Modus

ARIA hat zwei Arbeitsmodi:

- **User-Modus**: reduzierte Arbeitsansicht fuer den Alltag
- **Admin-Modus**: zusaetzliche System-, Routing-, Security-, Workbench- und Config-Seiten

Wenn Konfigurationsseiten fehlen, pruefe unter `/config/users`, ob **Admin aktiv** eingeschaltet ist.

## Chat, Aktionen und Details

Im Chat kannst du normal fragen oder natuerliche Arbeitsauftraege geben, zum Beispiel:

- `ist mein dns server ok`
- `check mal die festplatten von meinen servern und melde mir falls handlungsbedarf besteht`
- `pruef ob die api erreichbar ist`
- `zeige mir die folder auf dem share Ronny Fischer`
- `mach mir eine zusammenfassung der letzten it-security news`

ARIA versucht dann:

1. den Prompt mit Kontext anzureichern
2. passende Connections, Rezepte und vergangene Erfahrungen zu finden
3. bei Bedarf ein LLM einen begrenzten Action-Draft vorschlagen zu lassen
4. Policy und Guardrails entscheiden zu lassen: `allow`, `ask_user` oder `block`
5. die Aktion auszufuehren oder sauber zu erklaeren, warum sie nicht ausgefuehrt wird

Unter **Details** siehst du pro Antwort:

- Capability, Connection und Befehl/Pfad/Message
- Routing-Debug inklusive `agentic_source`, Draft/Policy/Runtime-Grenze
- Token-Anzahl und USD-Kosten, wenn ein LLM oder Embedding genutzt wurde
- Laufzeit
- Quellen bei RAG/Web/RSS-Antworten

## Bestaetigungen

Ausgehende oder potentiell wirkungsvolle Aktionen koennen auf `ask_user` gehen. Dann zeigt ARIA im Chat einen Button wie **Aktion ausfuehren**.

Beispiele:

- Discord-Nachricht senden
- Webhook ausloesen
- spaeter weitere nicht-read-only Aktionen

Read-only Aktionen wie `df -h`, Healthchecks oder RSS-Lesen koennen direkt laufen, sofern Guardrails sie erlauben.

## Memory

ARIA nutzt Qdrant fuer semantische Erinnerung.

Wichtig:

- **Fakten** und **Praeferenzen** sind langfristig
- **Session-Kontext** und Rollups helfen bei Arbeitsverlauf
- **Dokument-Collections** dienen RAG-Uploads
- **Experience Memory** speichert erfolgreiche sichere Aktionsmuster als Planner-Kontext, nicht als blinde Executor-Automatik
- fluechtige Momentaufnahmen aus SSH/RSS/SMB werden nicht pauschal in Memory geschrieben

Auf `/memories` kannst du Erinnerungen ansehen, suchen, bearbeiten, loeschen und exportieren. `/memories/map` zeigt Collections, Dokumentgruppen, Rollups und Memory-Struktur.

## Notizen

Unter `/notes` gibt es einen eigenstaendigen Markdown-Arbeitsbereich mit Ordnernavigation, Kartenansicht und Editor. Notizen sind bewusst von Memory getrennt, koennen aber fuer Suche indiziert werden.

## Connections

Connections sind explizite Profile zu externen Systemen. Gute Metadaten sind wichtig:

- Titel
- Kurzbeschreibung
- Aliase
- Tags
- Notizen zum Zweck der Verbindung

Diese Felder sind nicht nur Deko. ARIA nutzt sie fuer Routing, semantische Zielauswahl und LLM-Kontext.

Aktuelle Connection-Familien:

- SSH / SFTP / SMB
- RSS und beobachtete Webseiten
- Discord / Webhook / HTTP API
- SearXNG Websuche
- Google Calendar read-only
- SMTP / IMAP / MQTT

## Rezepte

Rezepte sind das sichtbare Automationsmodell. Legacy-Skills sind nur noch Kompatibilitaetsbruecken.

Ein Rezept ist ein JSON-Manifest mit:

- Triggern und Beschreibung
- Connection-Refs
- geordneten Steps
- optionalen LLM-Transforms
- Guardrail-/Bestaetigungslogik

Wichtige Step-Typen:

- `ssh_run`
- `sftp_read` / `sftp_write`
- `smb_read` / `smb_write`
- `rss_read`
- `llm_transform`
- `discord_send`
- `chat_send`

`llm_transform` nimmt technische Step-Ausgaben und macht daraus eine nuetzliche Zusammenfassung. `chat_send` schreibt das Ergebnis direkt in den Chat.

## RSS und News-Digests

RSS-Antworten sollen nicht nur sagen, dass es Treffer gibt. ARIA liefert fuer Digest-Prompts Titel, Quelle, Datum, Kurztext und Link, wenn der Feed einen Link bereitstellt.

Beispiele:

- `mach mir eine zusammenfassung der letzten it-security news`
- `was gibt es neues bei security news`

## Statistiken, Tokens und Kosten

`/stats` zeigt:

- Gesamt- und Durchschnittskosten
- Chat-/Embedding-Token nach Modell
- Requests nach Quelle
- Pricing Coverage
- unbepreiste Modelle
- LiteLLM-Preislistenstatus
- Routing-/Gateway-Audit

ARIA nutzt die LiteLLM-GitHub-Preisliste als Primaerquelle, ohne das LiteLLM-Python-Paket zu installieren. Die letzte gute Preisliste wird lokal gecached. Eigene Preise und Aliase koennen in der Pricing-Admin-UI unter `/stats` gepflegt werden.

Wichtig: Auch interne LLM-Aufrufe fuer Routing, RSS-Zusammenfassungen, Guardrail-Entscheide und Experience Memory muessen ueber die zentrale Usage-Metering-Schicht laufen. Wenn ein Action-Detail `0 tokens` zeigt, obwohl klar ein LLM genutzt wurde, ist das ein Bug.

## Updates

Der sichere Public-Pfad ist `aria-setup` / Managed Compose. Der Update-Helper aktualisiert gezielt nur den `aria` Service und laesst Qdrant, SearXNG, Valkey und Volumes unangetastet.

Vor einem Recreate prueft der Host-Update-Helper den geplanten Host-Port. Wenn ein anderer Prozess oder Container den Port belegt, bricht das Update vor Veraenderungen am laufenden Service ab.

## Security

ARIA ist fuer kontrollierte Umgebungen gebaut:

- Login und signierte Sessions
- Secure Store fuer API-Keys und Tokens
- CSRF-Schutz fuer Browser-Requests
- Guardrails fuer SSH/HTTP/File/Messaging-Aktionen
- One-Click-Bestaetigung fuer ausgehende Aktionen
- keine direkte Public-Internet-Empfehlung fuer die Alpha

## Troubleshooting

### ARIA waehlt das falsche Ziel

- Connection-Aliase und Kurzbeschreibung pruefen
- `/config/routing` oder `/config/workbench/routing` nutzen
- im Chat-Detail auf `routing_chain`, `semantic_llm`, `memory_hint` und `explicit_ref` achten

### Aktion wird blockiert

- Guardrail-Reason im Detail lesen
- pruefen, ob die Aktion read-only ist
- mutierende Aktionen brauchen bewusst engere Policies oder Bestaetigung

### Kosten wirken falsch

- `/stats` oeffnen
- Pricing Coverage pruefen
- `Preise aktualisieren` ausfuehren
- Modell-Aliase fuer Provider-/Proxy-Namen setzen

## Weiter lesen

- `/help?doc=quick-start`
- `/help?doc=memory`
- `/help?doc=connections`
- `/help?doc=skills`
- `/help?doc=pricing`
- `/help?doc=security`
- `/help?doc=releases`

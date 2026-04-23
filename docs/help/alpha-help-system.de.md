# ARIA Alpha Hilfe

Stand: 2026-04-07

Diese Seite ist die praktische Kurz-Hilfe für ARIA Alpha. Sie erklärt die wichtigsten Bereiche so, dass du direkt arbeiten kannst.

## Was ARIA Alpha gerade ist

ARIA ist aktuell vor allem ein persönlicher, selbst gehosteter AI-Assistent für LAN, VPN und Homelab.

Gut geeignet für:

- einen eigenen AI-Workspace im Browser
- Memory mit Qdrant
- Notizen als eigenen Markdown-Arbeitsbereich
- SSH / SFTP / SMB / RSS / Discord / HTTP-API / Webhook / Mail / MQTT
- Custom Skills, die mehrere Schritte automatisieren

Noch nicht als Ziel gedacht:

- offener Public-Internet-Betrieb
- großes Multi-User-/RBAC-System
- Enterprise-Deployment ohne technische Betreuung

## Erster Start

Beim ersten Start legst du den ersten Benutzer an. Dieser Benutzer wird automatisch Admin.

Danach solltest du zuerst diese Dinge prüfen:

1. `/config/llm` - Chat-Modell und API-Zugang
2. `/config/embeddings` - Embedding-Modell für Memory
3. `/stats` - Preflight, Qdrant, Modellstatus, Logs
4. `/config` - Connections zu deinen Systemen
5. `/skills` - Custom Skills importieren oder mit dem Wizard bauen

## Admin-Modus und User-Modus

ARIA hat zwei Arbeitsmodi:

- **User-Modus**: reduzierte Arbeitsansicht für den Alltag
- **Admin-Modus**: zusätzliche System-, Routing-, Security- und Config-Seiten

Wenn dir Konfigurationsseiten fehlen, prüfe unter `/config/users`, ob **Admin aktiv** eingeschaltet ist.

## Chat und Message-Details

Im Chat kannst du normal fragen oder über natürliche Prompts Connections und Skills triggern.

Unter **Details** siehst du pro Antwort unter anderem:

- welcher Intent / Skill / Capability genutzt wurde
- Token-Anzahl
- Kosten in USD, falls ARIA für das Modell Preise kennt
- Laufzeit

Wenn du bei einer Antwort `n/a` bei Kosten siehst, nutzt du entweder ein lokales Modell ohne Pricing oder der konkrete Modellname ist noch nicht in der Preisliste erfasst.

## Memory

ARIA nutzt Qdrant für semantische Erinnerung.

Wichtig:

- **Fakten** und **Präferenzen** sind eher langfristig
- **Kontext / Session** ist eher Tages- oder Arbeitsgedächtnis
- flüchtige Einmalfragen sollen möglichst **nicht** automatisch als Memory-Rauschen gespeichert werden
- reine Capability-Ergebnisse wie RSS-/SMB-/SSH-Momentaufnahmen werden **nicht pauschal** automatisch in Memory geschrieben

Auf `/memories` kannst du Erinnerungen:

- ansehen
- suchen
- bearbeiten
- löschen
- als JSON exportieren

Wenn du explizit etwas löschen willst, kannst du im Chat mit Formulierungen wie `vergiss ...` arbeiten oder direkt auf `/memories` löschen.

Wichtig zur Abgrenzung:

- `Memory` ist ARIAs semantisches Erinnern
- `Notizen` sind dein bewusst geschriebener Markdown-Bereich unter `/notes`
- Notizen werden zwar fuer Suche in Qdrant indiziert, gehoeren aber produktisch **nicht** in den Memory-Bereich

## Notizen

Unter `/notes` findest du einen eigenstaendigen Arbeitsbereich:

- links Ordnernavigation wie in einem kleinen Explorer
- rechts ein Zettel-Board mit Vorschau
- darunter den Editor fuer die ausgewaehlte Notiz

Notizen sind absichtlich:

- editierbar
- exportierbar als Markdown
- getrennt von Memory

ARIA kann Notizen auch im Chat anlegen, z. B. ueber Formulierungen wie:

- `notiere ...`
- `halte fest ...`

## Connections

Unter `/config` verwaltest du externe Verbindungen.

Grundprinzip:

- **Neu** legt ein neues Profil an
- Klick auf eine bestehende Statuskarte öffnet direkt den Edit-Modus
- Titel, Kurzbeschreibung, Aliase und Tags helfen ARIA beim Routing

Je besser Titel / Aliase / Tags gepflegt sind, desto eher trifft ARIA bei freien Chat-Fragen die richtige Connection.

### SSH / SFTP / SMB

- SSH beschreibt, wie ARIA einen Server erreicht
- SFTP kann SSH-Daten aus einem bestehenden SSH-Profil übernehmen
- SMB verbindet ARIA mit einem Share
- Guardrails können erlaubte Aktionen oder Pfade begrenzen

### Discord / Webhook / HTTP-API

- Discord ist aktuell vor allem als Webhook-Ziel und Skill-Output-Kanal gedacht
- für Discord-Connections kannst du z. B. Testposts und `Skill-Ziel erlauben` setzen
- HTTP-API und Webhook sind für gezielte Request-/Send-Flows gedacht

### SearXNG / Websuche

- SearXNG ist fuer ARIA ein separater Suchdienst im Stack, aehnlich zur Trennung von Qdrant
- ARIA nutzt nur die JSON-Suche von SearXNG, nicht den internen Code des Projekts
- die Stack-URL ist in ARIA standardmaessig fest hinterlegt:
  - `http://searxng:8080`
- pro Profil konfigurierst du dann nur noch:
  - Sprache
  - SafeSearch
  - wenige Kategorien
  - wenige bevorzugte Engines
  - Trefferzahl
  - Zeitbereich
- fuer Routing helfen klare Profilnamen und Tags, z. B. `youtube` fuer Videos oder `startpage` fuer Buecher
- im Chat kannst du dann bewusst Formulierungen wie `websuche ...` oder `recherchiere im web ...` verwenden

### Beobachtete Webseiten

- fuer Seiten ohne RSS-Feed
- du gibst vor allem die URL an
- ARIA kann Titel, Kurzbeschreibung, Tags und Gruppe automatisch vorschlagen
- spaeter lassen sich solche Quellen gut mit Websuche und Notizen kombinieren

### Google Calendar

- erster persoenlicher `read-only` Produktpfad
- eigener Setup-Flow auf der Connection-Seite mit Google-Links pro Schritt
- gedacht fuer alltaegliche Fragen wie:
  - `was steht heute an?`
  - `wann ist mein naechster termin?`

### RSS

RSS ist in ARIA besonders nützlich, wenn du viele Feeds kuratieren und per LLM verdichten willst.

Auf der RSS-Seite kannst du:

- Feeds einzeln anlegen
- OPML importieren / exportieren
- Feeds nach Gruppen/Kategorien organisieren
- pro Feed `Jetzt pingen`
- mit `Check mit LLM` Titel, Kurzbeschreibung, Aliase und Tags vorschlagen lassen
- mit `Kategorien mit LLM aktualisieren` Feeds ohne manuell gesetzte Gruppe automatisch einsortieren

Hinweise:

- das globale Ping-Intervall gilt für alle RSS-Feeds
- ARIA staffelt die Fälligkeit intern pro Feed, damit nicht alle gleichzeitig pingen
- die RSS-Seite zeigt in der Übersicht primär den letzten bekannten Cache-Status
- wenn eine URL JSON statt RSS/Atom liefert, lege sie besser unter HTTP-API an

## Skills

Custom Skills sind JSON-Manifeste mit einer Liste von Steps.

Im Skill Wizard kannst du:

- Skills erstellen / bearbeiten
- Steps hinzufügen, duplizieren, verschieben, löschen
- Skills aktivieren / deaktivieren
- Skills importieren / löschen

Wichtige Step-Typen:

- `ssh_run`
- `sftp_read` / `sftp_write`
- `smb_read` / `smb_write`
- `rss_read`
- `llm_transform`
- `discord_send`
- `chat_send`

### `llm_transform` vs `chat_send`

- `llm_transform` nimmt eine technische Step-Ausgabe und lässt ein LLM daraus eine bessere Zusammenfassung oder Auswahl bauen
- `chat_send` schreibt das Ergebnis direkt in den Chat

Platzhalter im Skill-Prompt:

- `{prev_output}` = Ergebnis des direkt vorherigen Steps
- `{s1_output}`, `{s2_output}`, ... = gezielt auf frühere Steps zugreifen
- `{query}` = ursprüngliche Chat-Frage

Damit kannst du z. B. mehrere RSS-Feeds in mehreren `rss_read`-Steps holen und danach in einem `llm_transform` eine kuratierte Morgen-Zeitung daraus bauen.

## Mitgelieferte Samples

ARIA bringt Beispiel-Skills und Beispiel-Connections mit.

- auf `/skills` kannst du Sample-Skills direkt importieren
- auf `/config` kannst du Sample-Connections direkt importieren

Die Samples sind bewusst Templates. In der Praxis musst du meistens Refs, Hosts, URLs oder Discord-Webhooks auf deine Umgebung anpassen.

## Statistiken

Auf `/stats` findest du:

- aktuelle ARIA-Version
- Token- und Kostenstatistik
- ARIA RAM und Qdrant-DB-Größe
- Startup Preflight
- Systemzustand
- Live-Status aller konfigurierten Verbindungen
- Aktivitäten & Runs

Die grünen/gelben/roten Lämpchen zeigen dir schnell, wo etwas gesund ist und wo du genauer hinschauen solltest.

### Preise aktualisieren

Wenn du OpenAI / Anthropic / OpenRouter nutzt und Kosten sehen willst, kannst du in `/stats` **Preise aktualisieren** ausführen.

Lokale Modelle wie Ollama können absichtlich ohne USD-Preis erscheinen.

### Statistik-Reset

Mit Statistik-Reset kannst du Token-/Kosten-/Activity-Daten zurücksetzen. Das löscht **nicht** deine Memories, Skills oder Connections.

## Security

Für Public Alpha gilt klar:

- ARIA bitte **nicht direkt offen ins Internet stellen**
- besser nur im LAN oder über VPN / WireGuard nutzen
- Admin-Modus nur aktiv lassen, wenn du wirklich konfigurieren willst
- bei SSH / SMB / SFTP mit Guardrails und möglichst begrenzten Rechten arbeiten
- API-Keys und Secrets gehören in den Secure Store / lokale Secret-Konfiguration, nicht in öffentliche Doku oder Git

## Troubleshooting

### Chat antwortet nicht sinnvoll

Prüfe:

- `/config/llm`
- `/config/embeddings`
- `/stats` -> Preflight und Systemzustand

Wenn Antworten mit `finish_reason=length` abbrechen, ist `Max Tokens` wahrscheinlich zu niedrig.

### Memory wirkt leer oder ungenau

Prüfe:

- ist Qdrant erreichbar?
- ist das Embedding-Modell korrekt gesetzt?
- ist Auto-Memory aktiv?
- gibt es überhaupt passende Fakten/Präferenzen in `/memories`?

### Skill triggert nicht

Prüfe:

- Skill ist aktiv?
- Trigger / Beschreibung / Aliase sind klar genug?
- Custom-Skill-Routing kollidiert nicht mit einem zu generischen Prompt?
- verwendete Connection-Refs stimmen?

### Connection-Test ist rot

Prüfe:

- Host / URL / Port / Credentials
- Netzwerk-Erreichbarkeit vom ARIA-Container aus
- Guardrails / erlaubte Aktionen
- bei RSS: ist es wirklich RSS/Atom und nicht JSON?

## Wo du weiterliest

Unter `/help` findest du diese Kurz-Hilfe.

Unter `/product-info` findest du zusätzlich:

- Produktüberblick
- Feature-Liste
- Architektur

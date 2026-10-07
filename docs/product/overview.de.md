# ARIA - Produktueberblick

## Was ARIA ist

ARIA ist ein kleiner, modularer KI-Assistent fuer Menschen, die Kontrolle statt Plattform-Wildwuchs wollen.

ARIA laeuft lokal, haelt seine Architektur nachvollziehbar und kombiniert:

- eine browser-first Chat-Oberflaeche
- strukturiertes Gedächtnis mit Qdrant
- rezeptgesteuerte Automatisierung
- modulare Verbindungen zu externen Systemen
- explizite Sicherheits- und Rollen-Grenzen

ARIA versucht bewusst **nicht**, eine riesige "alles kann alles"-KI-Suite zu werden.
Das Ziel ist ein schlankes, pruefbares und erweiterbares System.

---

## Kernidee

**Browser oeffnen und loschatten.**

ARIA ist GUI-first gebaut:

- keine API-first-Komplexitaet fuer normale Nutzung
- keine React-/Node-/Buildchain-Pflicht
- kein grosser Framework-Stack, der die eigentliche Logik versteckt

Das Ziel ist einfach:

> Ein System, eine Konfiguration, eine klare UI, echte Faehigkeiten.

---

## Was ARIA anders macht

### 1. Klein durch Design

ARIA ist absichtlich leichtgewichtig.

ARIA soll nicht sein:

- ein schwerer OpenWebUI-Klon
- ein Workflow-Labyrinth
- eine Blackbox-Agentenplattform

ARIA soll sein:

- schnell zu verstehen
- guenstig zu betreiben
- gut anpassbar
- realistisch selbst hostbar

### 2. Modular statt hart verdrahtet

ARIA bewegt sich in Richtung einer faehigkeitsbasierten Architektur.

Das System denkt zuerst in Aktionen wie:

- `file_read`
- `file_write`
- `feed_read`
- `webhook_send`
- `api_request`

Erst danach wird entschieden, welche konkrete Verbindung oder welcher Transport genutzt wird.
Das macht ARIA erweiterbar und bereitet spaetere benutzerdefinierte Module vor.

### 3. Token-bewusst und praktisch

ARIA ist mit Token-Disziplin gebaut.

Es vermeidet unnoetigen Orchestrierungsaufwand und versucht:

- Prompts kompakt zu halten
- Routing wo moeglich deterministisch zu machen
- Gedächtnis nuetzlich statt laut werden zu lassen

### 4. Lokal-first und self-hosting-freundlich

ARIA kann im lokalen Netz, auf einem kleinen Server oder in einem Container-Setup laufen.

Es ist gedacht fuer Menschen, die wollen:

- lokale Kontrolle
- berechenbares Hosting
- klares Deployment-Verhalten
- weniger Abhaengigkeit von Drittanbieter-SaaS

---

## Was ARIA heute kann

### Chat und Gedächtnis

- browserbasierte Chat-UI
- typisiertes Gedächtnis fuer Fakten, Praeferenzen, Session-Kontext und verdichtetes Wissen
- Dokument-Collections fuer RAG-Uploads
- Auto-Memory und manuelle Memory-Pflege
- Memory-Suche und Wartungsansichten
- eigenstaendiger Notizen-Bereich unter `/notes`
- Markdown-first Notizen mit Qdrant-gestuetzter semantischer Suche
- Provider-native Websuche, wenn das konfigurierte Modell Web-Tools unterstuetzt
- beobachtete Webseiten als leichte Quellen fuer Seiten ohne RSS

### Rezepte und Automatisierung

- gespeicherte Rezept-Manifeste als JSON
- schrittbasierte Rezept-Pipeline
- Rezept-Wizard in der UI
- Import/Export fuer eigene Rezepte
- Runtime-Ausfuehrung fuer strukturierte Rezeptschritte

### Verbindungen

ARIA unterstuetzt mehrere Verbindungstypen mit eigenen Konfigurationsseiten, Health-Checks, Statusanzeigen und Routing-Integration.

Aktuelle Verbindungsfamilien:

- `SSH`
- `Discord`
- `SFTP`
- `SMB`
- `Webhook`
- `HTTP API`
- `Google Calendar`
- `Watched Websites`
- `RSS`
- `SMTP`
- `IMAP`
- `MQTT`

Diese Eintraege sind nicht nur Konfiguration. ARIA verdrahtet sie schrittweise mit natuerlichen Chat-Faehigkeiten.

### Faehigkeitsbasierte Aktionen

Beispiele:

- entfernte Dateien via `SFTP` lesen und schreiben
- Dateibereiche via `SMB` lesen
- `RSS`-Feeds lesen
- Websuche ueber konfigurierte Provider-Web-Tools
- kommende Termine ueber read-only `Google Calendar` iCal-Feeds abrufen
- Nachrichten an `Discord` senden
- konfigurierte `HTTP APIs` aufrufen
- `Webhook`-Ziele ansprechen
- Mail via `SMTP` / `IMAP` senden und lesen
- Nachrichten an `MQTT` publizieren
- Markdown-Notizen als zusaetzlichen Kontext fuer Recherche nutzen

### Sicherheit und Betrieb

- Login und Rollen
- Admin-Modus vs. User-Modus
- sicherer Secret Store
- Config-UI mit Zugriffsschutz auf Routenebene
- Statistik- und Runtime-Health-Ansichten
- Loesch-, Bearbeitungs- und Test-Flows fuer Verbindungen

Aktuelle ALPHA-Grenze:

- ARIA ist noch kein vollstaendiges Multi-User-System
- der aktuelle User-Modus ist eine reduzierte Arbeitsansicht
- er trennt Alltagsnutzung von Systemkonfiguration
- Ownership, Sharing und RBAC fuer Rezepte und Ressourcen sind als eigener Architekturblock geplant

---

## Warum das wichtig ist

ARIA ist nicht nur ein Chat-Frontend.

ARIA wird zu einer kompakten lokalen Automatisierungs- und Assistenzschicht, die:

- relevanten Kontext behalten kann
- explizite User-Notizen getrennt vom Gedächtnis fuehrt
- mit echten Systemen sprechen kann
- nachvollziehbar bleibt
- von einer Person oder einem kleinen Team betrieben werden kann

Nuetzliche Einsatzbereiche:

- Homelab-Umgebungen
- interne Team-Assistenten
- self-hosted KI-Workflows
- lokale operative Dashboards
- kleine Automatisierungs-Hubs

---

## Designprinzipien

### Browser-first

Der Browser ist die Hauptoberflaeche. Normale Nutzung soll keine CLI-Workflows brauchen.

### Sicherheit vor Bequemlichkeit

Wenn etwas riskant ist, soll ARIA:

- es per Rolle begrenzen
- explizit bestaetigen lassen
- den Ausfuehrungspfad nachvollziehbar halten

### Modulares Wachstum

Neue Faehigkeiten sollen als Module mit klaren Grenzen wachsen, nicht als immer groesserer Monolith.

### Lokale Kontrolle

ARIA soll so funktionieren, dass der Betreiber versteht, wo Konfiguration, Daten, Logs und externe Verbindungen liegen.

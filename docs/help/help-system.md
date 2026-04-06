# ARIA - Hilfe-System / Doku-Hub

Stand: 2026-04-06

Zweck:
- beschreibt die aktuelle Help-Richtung von ARIA
- dokumentiert bewusst den einfacheren und nuetzlicheren Weg fuer die ALPHA-Linie
- dient als Grundlage fuer lokale `/help`-Seiten und die GitHub-Wiki aus denselben Quelldateien

## Aktuelle Richtung

ARIA setzt aktuell **nicht** auf ein grosses kontextsensitives Hilfe-System mit Info-Icons an vielen Einzelstellen.

Der aktuelle Fokus ist:

- eine gute, zentrale `/help`-Seite direkt im Produkt
- dieselben Markdown-Quellen lokal und auf GitHub-Wiki nutzen
- Hilfe nur einmal pflegen
- praktische, eher produktnahe Doku statt vieler kleiner UI-Erklaerfetzen

Das bringt fuer ARIA derzeit den groesseren Nutzen:
- wenig Pflegeaufwand
- hohe Sichtbarkeit fuer Nutzer
- gute Grundlage fuer Public Alpha und Self-Hosting
- spaeter trotzdem erweiterbar

## Was `/help` heute sein soll

`/help` ist ein lokaler Docs-Hub fuer:

- Quick Start
- Memory und Dokumenten-RAG
- Skills
- Connections
- Releases / Upgrades
- Pricing
- Security

Die Quellen dafuer liegen primaer in:
- `docs/wiki/`
- `docs/help/`

Damit gilt:
- GitHub-Wiki und lokale Hilfe greifen moeglichst auf dieselben Markdown-Dateien zu
- Produktdoku wird nicht doppelt gepflegt
- fuer lokalisierte Help-Seiten koennen passende Sprachvarianten wie `Quick-Start.de.md` oder `pricing.en.md` neben der Basisdatei liegen

## Was bewusst nicht Prioritaet hat

Noch nicht aktueller Fokus:
- Help-Icons an sehr vielen einzelnen Formularfeldern
- Popover pro UI-Feld
- KI-generierte Live-Hilfe
- grosses Tutorial-System
- separate Doku-Engine

## Denkbares Datenmodell

Beispiel einer späteren zentralen Help-Struktur:

```json
{
  "llm.setup": {
    "title": "LLM-Konfiguration",
    "body": "Hier legst du Modell, API-Endpunkt, API-Key, Temperatur und Token-Limit fest."
  },
  "rss.aliases": {
    "title": "Aliase / Suchbegriffe",
    "body": "Diese Begriffe helfen ARIA, freie Chat-Fragen dem richtigen RSS-Feed zuzuordnen."
  }
}
```

Mögliche Speicherorte später:
- `aria/i18n/help.de.json`
- `aria/i18n/help.en.json`
- oder `help/*.json` / `help/*.yaml`

## Erste sinnvolle Help-Texte

### `first_run.bootstrap`

**Titel:** Erster Start

**Text:**  
Beim ersten Start legst du den ersten ARIA-Benutzer an. Dieser erste Benutzer wird automatisch Admin und kann danach LLMs, Connections, Skills und Security-Einstellungen konfigurieren.

### `llm.setup`

**Titel:** LLM-Konfiguration

**Text:**  
Hier legst du fest, welches Chat-Modell ARIA nutzt, wo der API-Endpunkt liegt, welcher API-Key verwendet wird und wie viele Tokens maximal generiert werden dürfen. Wenn Antworten abgeschnitten werden, ist `Max Tokens` meist zu niedrig.

### `embeddings.setup`

**Titel:** Embeddings

**Text:**  
Embeddings werden für semantische Memory-Suche in Qdrant genutzt. Das Embedding-Modell kann unabhängig vom Chat-Modell konfiguriert werden. Wenn Memory-Recall schlecht wirkt, ist dieses Setup ein wichtiger Prüfpunkt.

### `memory.auto_memory`

**Titel:** Auto-Memory

**Text:**  
Auto-Memory bestimmt, ob ARIA aus normalen Chat-Antworten automatisch Erinnerungen ableitet. Das ist praktisch für persönliche Fakten und Präferenzen, kann aber bei zu aggressiver Einstellung auch unnötiges Memory-Rauschen erzeugen.

### `memory.forget`

**Titel:** Vergessen / Memory löschen

**Text:**  
Mit Forget entfernst du gespeicherte Erinnerungen gezielt wieder aus Qdrant. Leere Collections werden danach aufgeräumt. Ein exportierbares Memory-Archiv ist als späteres Feature geplant.

### `connections.metadata`

**Titel:** Titel, Kurzbeschreibung, Aliase, Tags

**Text:**  
Diese Metadaten sind nicht nur Beschreibungstext. ARIA nutzt sie beim Routing, um freie Chat-Fragen der passenden Connection oder dem passenden Skill zuzuordnen. Gute Aliase und kurze Beschreibungen verbessern die Trefferquote deutlich.

### `ssh.profile`

**Titel:** SSH-Profil

**Text:**  
Ein SSH-Profil beschreibt, wie ARIA einen Server erreicht: Host, Port, User, Authentifizierung und Timeout. Was ARIA dort konkret ausführen soll, wird meist über Skills oder Capability-Flows definiert.

### `rss.group`

**Titel:** RSS-Gruppe / Kategorie

**Text:**  
Die Gruppe ordnet Feeds thematisch in der RSS-Übersicht. Du kannst bestehende Gruppen auswählen oder eine neue Gruppe frei eintragen. Manuell gesetzte Gruppen werden von `Kategorien mit LLM aktualisieren` nicht überschrieben.

### `rss.aliases`

**Titel:** RSS-Aliase und Tags

**Text:**  
Aliase, Tags, Titel und Kurzbeschreibung helfen ARIA, Fragen wie „was gibt es auf heise?“ dem richtigen Feed zuzuordnen. `Check mit LLM` kann diese Felder automatisch vorschlagen oder ergänzen.

### `rss.poll_interval`

**Titel:** Globales RSS-Ping-Intervall

**Text:**  
Dieses Intervall gilt global für alle RSS-Feeds. ARIA staffelt die Feed-Fälligkeit intern pro Feed, damit nicht alle Feeds gleichzeitig geprüft werden. Die RSS-Seite zeigt primär den letzten bekannten Cache-Status.

### `skills.triggers`

**Titel:** Skill-Trigger

**Text:**  
Trigger sind Formulierungen oder Schlüsselbegriffe, mit denen ARIA einen Custom Skill aus freien Chat-Prompts erkennt. Je klarer Trigger und Skill-Beschreibung sind, desto zuverlässiger gewinnt der Skill gegenüber generischem Chat.

### `skills.step_order`

**Titel:** Step-Reihenfolge

**Text:**  
Custom Skills laufen in der sichtbaren Reihenfolge ab. Steps können dupliziert und verschoben werden. Das ist besonders hilfreich, wenn du denselben SSH-Check auf mehrere Server kopieren möchtest.

### `skills.llm_transform`

**Titel:** `llm_transform` vs `chat_send`

**Text:**  
`llm_transform` formt technische Step-Ausgaben in eine natürlichere Zusammenfassung um. `chat_send` gibt eine Message direkt in den Chat aus. Für angenehmere Skill-Antworten ist oft `ssh_run -> llm_transform -> chat_send` sinnvoll.

### `guardrails.ssh`

**Titel:** Guardrails

**Text:**  
Guardrails begrenzen, welche Befehle oder Aktionen über eine Connection erlaubt sind. Gerade bei SSH ist das wichtig, damit ARIA nicht still riskante oder unerwartete Kommandos ausführt.

### `stats.costs`

**Titel:** Kosten / Pricing

**Text:**  
Kosten werden nur angezeigt, wenn ARIA für das genutzte Modell einen Preis kennt. Für OpenAI/Anthropic nutzt ARIA eine LiteLLM-Preisliste, für OpenRouter eine API-Synchronisierung. Lokale Modelle können bewusst ohne Kostenwert erscheinen.

### `stats.preflight`

**Titel:** Startup Preflight

**Text:**  
Preflight zeigt, ob zentrale Grundlagen wie Prompt-Dateien, Memory/Qdrant, Chat-LLM und Embeddings grundsätzlich bereit sind. Die Status-Lämpchen zeigen schnell, wo ein Setup-Problem liegt.

## Umsetzungsvorschlag

Minimaler technischer Ansatz:
- Help-Key pro Block/Feld im Template
- zentraler Help-Loader liest Help-Texte aus JSON/YAML
- kleines Jinja-Partial oder Makro rendert Info-Icon + toggelbare Help-Box
- Texte pro Sprache getrennt pflegen

Warum so:
- kleine erste Implementierung
- später ohne Template-Gewitter austauschbar
- übersetzbar
- gut erweiterbar für Public Alpha

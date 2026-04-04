# ARIA — Alpha Build Log

Stand: 2026-04-03

Zweck:
- nachvollziehen, **was bereits in Alpha-Builds gelandet ist**
- festhalten, **was auf `dev` schon vorbereitet ist**
- Build-Versionen und inhaltliche Aenderungen zusammen sichtbar machen

## Bereits gebaut

### alpha8

- Skill-Loeschen auf `/skills`
- Skill-Loeschen direkt im Wizard
- neue sauber benannte Background-Assets
- `Nodes Field` als zusaetzlicher Background
- Theme-/Background-Einbindung aktualisiert

### alpha9

- Logo-Fix im Build
- Skill-Wizard:
  - `Schritt duplizieren`
  - `Step ID` aus der sichtbaren UI entfernt
  - `SSH Command` als groesseres Feld mit hoeherem Limit
- neue Samples/Connections fuer:
  - `SMB`
  - `Discord`
  - `RSS`
- aktualisiertes Linux-Update-Sample

### alpha10

- Stats-Fix fuer `bepreiste Anfragen`
- `0.0`-Kosten zaehlen nicht mehr als bepreist
- fruehe Pipeline-Pfade loggen keine Fake-Preise mehr
- Release-Label:
  - `0.1.0-alpha10`

### alpha11

- Connection-UX auf den Connection-Seiten beruhigt:
  - bestehende Profile direkt anklickbar
  - `Bearbeiten` aus dem Kopfbereich entfernt
  - `Neu` als klarer Einstieg
  - im Create-Modus: `Zurueck zu Verbindungen`
- Skill-Wizard:
  - duplizierte Steps landen direkt unter dem aktuellen Step
  - Steps lassen sich nach oben/unten verschieben
  - Reihenfolge wird vor dem Speichern sauber neu nummeriert
- Custom-Skill-Prioritaet vor generischem Capability-Pfad
  - klar passende Skills gewinnen jetzt vor z. B. direktem Discord-Senden
- Release-Label:
  - `0.1.0-alpha11`

### alpha12

- Stats:
  - Qdrant-Groesse wird im separaten Docker-/Compose-Betrieb ueber Qdrant-Telemetrie/API ermittelt
  - `Startup Preflight` zeigt die vier Kernchecks auf Desktop als eine Reihe
- Release-Label:
  - `0.1.0-alpha12`

### alpha13

- Memory:
  - Chat-Forget raeumt leere Qdrant-Collections sofort auf
- Discord:
  - Skill-Error-Alerts werden gekuerzt/sanitized
  - Statuschips fuer `Testposts aktivieren` / `Skill-Ziel erlauben` sind klarer als Read-only-Anzeige gestaltet
- Connections:
  - SFTP `SSH-Daten uebernehmen` im Create-Modus speichert wieder korrekt ein neues Profil
  - RSS nutzt dieselbe `Neu` / Klick-auf-Karte-zum-Editieren-Logik wie die anderen Connection-Seiten
- UI:
  - Back-Pfeil sitzt sauber unter der Topbar und ist etwas sichtbarer
- Release-Label:
  - `0.1.0-alpha13`

### alpha14

- Stats / Statistics:
  - `Aktivitaeten & Runs` ist direkt in `/stats` integriert
  - der separate Menuepunkt `Aktivitaeten` ist aus dem User-Menue entfernt
  - Activity-KPIs stehen in einer kompakten 4er-Reihe mit Mobile-Fallback
- Pricing:
  - manueller Button `Preise aktualisieren` in `/stats`
  - OpenAI-/Anthropic-Preise werden aus `litellm.model_cost` in die lokale ARIA-Preisliste uebernommen
  - OpenRouter-Preise werden ueber `https://openrouter.ai/api/v1/models` synchronisiert
  - aktualisierte Preise werden in `config/config.yaml` persistiert
- Connections:
  - Karten aus `Live-Status aller Profile` sind jetzt der direkte Einstieg in den Edit-Modus
  - Zusatzbloecke wie `Geladenes Profil` / separate Direkt-Links sind entfernt
  - `ARIA_PUBLIC_URL` / `aria.public_url` wird fuer Host-/Discord-Links genutzt statt Docker-Bridge-IP
  - RSS-Save-Redirect auf `Zurueck zu Verbindungen` korrigiert
- RSS / OPML:
  - OPML Import/Export auf der RSS-Connection-Seite
  - OPML-Import erzeugt pro Feed ein eigenes RSS-Profil
  - doppelte Feed-URLs werden beim Import uebersprungen
  - pro RSS-Profil gibt es `poll_interval_minutes`
  - RSS-Seite nutzt bei frischem Status den Cache statt jeden Feed bei jedem Seitenaufruf live zu pingen
  - OPML-Export schreibt die RSS-Sammlung als OPML 2.0
- UI / i18n:
  - `Stats` heisst in DE jetzt `Statistiken`, in EN `Statistics`
- Release-Label:
  - `0.1.0-alpha14`

### alpha15

- Stats:
  - `Aktivitaeten & Runs` auf `/stats` unter `Live-Status aller konfigurierten Verbindungen` verschoben
- RSS:
  - OPML-Import-Upload repariert (`opml_file missing` / Multipart-CSRF)
  - `OPML Import / Export` als einklappbarer Block
  - RSS-Kategorien als einklappbare Gruppen
  - nach Klick auf einen Feed zeigt der Edit-Modus nur noch diesen Feed + Formular + Loeschen
- Release-Label:
  - `0.1.0-alpha15`

### alpha16

- LLM:
  - leere Provider-Antworten werden als sauberer `LLMClientError` behandelt
  - ARIA faellt dadurch nicht mehr still auf `Ich habe gerade keine Antwort erzeugt.` zurueck
- RSS:
  - `Jetzt pingen` fuer den aktuell gewaehlten Feed im Edit-Modus
  - `Kategorien mit LLM aktualisieren` ist jetzt ein klarer Button statt ein dezenter Link
  - EN-Label: `Refresh categories with LLM`
- Release-Label:
  - `0.1.0-alpha16`

### alpha17

- LLM:
  - Default `max_tokens` fuer neue Setups/Profile auf `4096` erhoeht
  - reduziert `finish_reason=length` bei normalen Chat-Antworten
- Pricing:
  - Kostenberechnung nutzt jetzt eine LiteLLM-Fallback-Preisliste
  - bekannte Modelle wie `gpt-5.1` bekommen dadurch auch dann USD-Kosten, wenn `pricing.chat_models` in der Config noch leer ist
- Release-Label:
  - `0.1.0-alpha17`

### alpha18

- Custom-Skill-Routing:
  - Description-Match entschaerft
  - generische Admin-/Storage-Fragen wie LVM/ZFS/Btrfs triggern den Linux-Updates-Skill nicht mehr nur wegen `Ubuntu` + `Server`
  - echte Linux-Update-Fragen triggern den Skill weiter
- RSS:
  - RSS-Verbindungstests nutzen jetzt einen browserartigen `User-Agent`
  - RSS-Skill-Reads nutzen denselben robusteren Header
  - behebt Feeds, die im Browser funktionieren, aber vorher in ARIA mit `HTTP Error 403: Forbidden` gescheitert sind
- Release-Label:
  - `0.1.0-alpha18`

### alpha19

- Mobile/iPhone:
  - `Admin aktiv` sitzt auf kleinen Screens rechts in der Menu-Zeile statt neben dem A.R.I.A.-Titel
  - Desktop bleibt unveraendert
- RSS:
  - RSS-Statuskarten auf der RSS-Seite nutzen beim Seitenaufbau nur noch den letzten Cache-Stand
  - bei fehlendem/abgelaufenem Cache wird **kein synchroner Live-Ping** mehr gestartet
  - stattdessen zeigt ARIA einen Hinweis und `Jetzt pingen` bleibt die explizite Live-Aktion pro Feed
  - Feed-Loeschen/Editieren blockiert dadurch nicht mehr 20-40 Sekunden wegen eines langsamen RSS-Endpunkts
  - RSS-Verbindungstests lesen mehr als den alten 8-KB-Ausschnitt und akzeptieren auch RSS-1.0-Roots wie `<rdf:RDF>`
  - behebt valide Feeds wie NVD/Debian, die vorher faelschlich mit `ungueltiges XML` rot wurden
  - RSS-Profile haben jetzt `group_name` als manuell setzbare Gruppe/Kategorie
  - OPML-Import uebernimmt die erste OPML-Kategorie als Start-Gruppe
  - OPML-Export nutzt `group_name` als Outline-Gruppe
  - `Kategorien mit LLM aktualisieren` sortiert nur noch Feeds ohne manuell gesetzte Gruppe neu
- Release-Label:
  - `0.1.0-alpha19`

### alpha20

- RSS:
  - Feld `Gruppe / Kategorie` bietet jetzt Dropdown-Vorschlaege aus bestehenden Gruppen, bleibt aber frei editierbar fuer neue Kategorien
  - Feed-URL-Dedupe normalisiert URLs vor Vergleich/Speicherung
  - Varianten wie `/feed`, `/feed/`, Default-Port `:443`, Fragment-Hashes und Tracking-Parameter wie `utm_*`/`fbclid` werden zusammengefuehrt
  - JSON-URLs in RSS liefern jetzt eine klare Fehlermeldung mit Hinweis auf HTTP-API-Connections
  - auf RSS-Detailseiten geht `Zurueck zur RSS-Uebersicht` wieder direkt nach `/config/connections/rss`
  - lokale RSS-Suche nur ueber RSS-Titel, URL, Ref, Gruppe und Tags
  - passende RSS-Gruppen klappen bei aktiver Suche automatisch auf
  - RSS-Gruppen werden alphabetisch sortiert
  - RSS-Gruppenuebersicht nutzt ein dichteres responsives 2-3-Spalten-Grid mit Mobile-Fallback
- Release-Label:
  - `0.1.0-alpha20`

### alpha21

- RSS:
  - globales `Ping-Intervall` fuer alle RSS-Feeds statt pro Feed einzeln pflegen
  - alle bestehenden RSS-Profile werden beim Speichern des globalen Intervalls auf denselben Wert synchronisiert
  - RSS-Poll-Faelligkeit wird pro Feed stabil per Hash-Offset gestaffelt, damit nicht alle Feeds auf derselben Intervall-Kante faellig werden
  - lokale RSS-Suche blendet nicht passende Gruppen/Feeds wieder korrekt aus
  - das Suchfeld reagiert auch auf das kleine `x` zum Leeren
  - natuerlichere RSS-Fragen wie `was fuer news gibs auf heise` werden besser als RSS-Intent erkannt
  - RSS-Routing nutzt jetzt auch Titel, Kurzbeschreibung, Aliase und Tags der RSS-Profile
  - Button `Check mit LLM` im RSS-Metadatenblock fuellt Titel, Kurzbeschreibung, Aliase und Tags vor bzw. ergaenzt sie
- Statistiken:
  - `Startup Preflight` und `Systemzustand` zeigen Status jetzt nur noch als gruene/gelbe/rote Laempchen statt ausgeschriebener `OK/Warn/Error`-Labels
- Themes:
  - neue Themes `CyberPunk Pulse`, `8-Bit Arcade`, `Amber CRT` und `Deep Space`
- Release-Label:
  - `0.1.0-alpha21`

### alpha22

- Themes:
  - `CyberPunk Pulse` staerker Richtung Hot-Pink/Magenta gezogen, weniger violette Flaechen
- Docs / Release:
  - Doku-Struktur unter `docs/` und `project.docu/history/` aufgeraeumt
  - `Hilfe` und `Produkt-Info` als Read-only-Seiten im UI angebunden
  - `LICENSE` und `THIRD_PARTY_NOTICES.md` ergaenzt
  - `docs/product/roadmap.md` als GitHub-tauglicher Roadmap-Snapshot ergaenzt
  - `docs/release/github-release-notes-template.md` als Release-Notes-Vorlage ergaenzt
  - `CHANGELOG.md` `Unreleased`-Block mit dem aktuellen dev-Stand befuellt
  - `README.md` und zentrale Public-Docs sprachlich/funktional auf den aktuellen Public-Alpha-Stand geglaettet
  - neutrale Beispielwerte in `docker/aria-stack.env.example`, `docs/setup/portainer-deploy-checklist.md` und `docs/help/memory.md`
  - `.gitignore` um Python-/Build-Artefakte und lokale TARs erweitert
- Onboarding:
  - Bootstrap-/Admin-/User-Modus in Login-, Benutzer- und Security-UI klarer erklaert
- Statistiken:
  - Statistik-Reset mit `RESET`-Bestaetigung auf `/stats`
  - Qdrant-Groessenanzeige robuster fuer separates Compose-/Portainer-Qdrant-Volume vorbereitet
- Memory:
  - Auto-Memory filtert fluechtige Einmalfragen und reine Tool-/Action-Prompts beim automatischen Persistieren staerker heraus
  - echte Fakten/Preferences und deklarativer Nutzerkontext werden weiter gespeichert
  - Architekturentscheidung festgehalten: Capability-Ergebnisse werden bewusst **nicht** pauschal automatisch in Memory persistiert; spaeter nur ueber gezielte Summary-/State-Memory-Flows
  - Memory-Export als JSON-Download in `/memories`
  - gewichtetes Multi-Collection-Recall mit einem expliziten Regression-Test gegen Fact-vs-Session-Ranking abgesichert
- Mobile/iPhone:
  - Chat-Debug-Header bricht lange `Tages-Kontext`- und `Login-Session`-IDs jetzt sauber um, statt horizontalen Page-Overflow zu erzeugen
- Release-Label:
  - `0.1.0-alpha22`

### alpha23

- Themes:
  - `CyberPunk Pulse` nochmals pinker gezogen, waehrend Helper-/Meta-/Status-Texte und Chips im Theme gezielt auf neon-gruen `#00ff00` gehen
- Mobile/iPhone:
  - Chat-Scroller und Message-Bubbles auf vertikales Panning geklemmt
  - horizontale Drift/seitliches Mitschieben beim Scrollen weiter reduziert
  - lange Bubble-Inhalte, Meta-Badges und Details-Zeilen brechen jetzt konsequent innerhalb der Bubble um
- Packaging:
  - `docs/` wird jetzt ins Docker-Image kopiert, damit `/help` und `/product-info` im Container nicht mehr auf fehlende Markdown-/SVG-Dateien laufen
- UI / Doku-Navigation:
  - `Produkt-Info` aus dem Top-Menue entfernt und stattdessen als Kachel unter `/help` verlinkt
- Statistiken:
  - Qdrant-Groessenanzeige faellt bei `Telemetry · n Collections`, aber `0 B`, jetzt erst noch auf lokale Storage-Pfade zurueck
  - `0 B` aus Qdrant-Telemetrie blockiert dadurch nicht mehr den Volume-/Filesystem-Fallback
- Release-Label:
  - `0.1.0-alpha23`

### alpha24

- UI / Produkt-Info:
  - `Copy Pack`-Kachel aus `/product-info` entfernt; dort bleiben nur Overview, Feature-Liste und Architektur
- Themes:
  - `CyberPunk Pulse`: Buttons und Menu-Beschriftung neon-gruen, damit die Controls klarer gegen die pinken Flaechen stehen
  - `Deep Space`: dunklerer, violett-/nebula-lastiger Farbschnitt, damit das Theme weniger nach `Harbor Blue` aussieht
- Samples / Skills / Connections:
  - `samples/` wird jetzt ins Docker-Image kopiert, damit Sample-Skills, Sample-Connections und Guardrail-Beispiele im Container unter `/app/samples` verfuegbar sind
  - `/skills` zeigt mitgelieferte Sample-Skills aus `/app/samples/skills` direkt an und kann sie serverseitig per Klick importieren
  - `/config` zeigt mitgelieferte Sample-Connections aus `/app/samples/connections` direkt an und kann sie serverseitig in `config.yaml` importieren, ohne bestehende Refs zu ueberschreiben
  - neuer Sample-Skill `rss-morning-briefing-to-discord-template.json` fuer ein taegliches, per LLM kuratiertes Multi-RSS-Briefing nach Discord
  - Skill-Wizard erklaert bei `llm_transform` jetzt direkt die Platzhalter `{prev_output}` und `{s1_output}` / `{s2_output}` fuer Multi-Step-Aggregation
- Release-Label:
  - `0.1.0-alpha24`

## Auf `dev` vorbereitet fuer den naechsten Build

- Hilfe:
  - `docs/help/alpha-help-system.de.md` und `docs/help/alpha-help-system.en.md` als praktische, menschenlesbare Alpha-Kurzhilfe in DE/EN ergaenzt
  - `/help` zeigt jetzt je nach aktiver UI-Sprache diese Alpha-Hilfe statt den internen Help-System-Entwurf `docs/help/help-system.md` direkt zu rendern
- Chat-Toolbox:
  - Skill-Eintraege zeigen jetzt den eigentlichen Skill-Namen als Titel, einen kleinen `/skill`-Badge und darunter Beschreibung/Beispiel-Trigger
  - lange Skill-Titel und Hinweise koennen in der Toolbox sauber umbrechen statt unsichtbar abgeschnitten zu werden
- Menue:
  - `Hilfe` sitzt jetzt nach `Einstellungen` und vor `Benutzer`
- `/stats` -> `Systemzustand`: ARIA Runtime, Model Stack, Memory / Qdrant, Security Store und Activities / Logs bekommen jetzt ebenfalls die normalen Status-Laempchen
- Repo-/Privacy-Sweep:
  - persoenliche Dev-Host-Defaults aus `docker/pull-from-dev.sh` entfernt
  - `config/secrets.env` neutralisiert
  - Root-Artefakte `=1.2` und `=2.1` entfernt
  - `docs/setup/portainer-deploy-checklist.md` von `/home/fischerman/ARIA` auf neutraleren Beispielpfad umgestellt

## Noch offen / weiter sammeln

- Docker-Hub-Hinweis auf neue Version statt In-App-Update
- Memory-Export auf `prod` live gegen echte Qdrant-Daten testen
- weitere Single-User-/Personalisierungs-Polishes

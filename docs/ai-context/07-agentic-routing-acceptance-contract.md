# ARIA Agentic Routing Acceptance Contract

Stand: 2026-09-01

Freigaberegel: Nur `FREIGABE: CODE` und `FREIGABE: BUILD` gemaess AGENTS.md. Analyse, Postmortem und Fix-Design sind Arbeitsschritte innerhalb CODE, keine zusaetzlichen Freigaben. Die E2E-Matrix bleibt vor jeder Verhaltensaenderung Pflicht.

Diese Datei ist ein verbindlicher Arbeitsvertrag fuer AI/Codex-Arbeit an ARIA. Sie existiert, weil mehrere interne Alpha-Fixes zwar lokale Tests bestanden, im Live-Verhalten aber neue Loecher in Routing, Web, Runtime-Actions, Source Authority, Confirmation und Latenz aufgerissen haben.

## Oberste Arbeitsregel

Kein Fix an ARIA-Routing, Web-Suche, Runtime-Actions, Source Authority, Guardrails oder Confirmation gilt als serioes, solange nicht zuerst die betroffene End-to-End-Wirkstrecke belegt wurde:

Userprompt -> MetaCatalog/TurnPlan -> Context/Action-Auswahl -> Skill/Runtime -> Composer/UI -> sichtbare Antwort.

Codex darf nicht behaupten, ein Fix sei "im richtigen Layer", wenn nur eine Teilfunktion, ein Helper oder ein isolierter Skill-Test betrachtet wurde.

## Vorgehen Vor Jeder Code-Aenderung

Vor Code-Aenderungen muss Codex eine kurze Abnahmematrix fuer den konkreten Problemtyp erstellen oder erweitern. Die Matrix muss enthalten:

- Problemklasse: generische Klasse des Fehlers, nicht nur der sichtbare Einzelfall.
- Prompt: echter User-Prompt oder minimaler reproduzierbarer Prompt.
- Erwarteter Pfad: erlaubte Surface/Action/Skill-Route.
- Verbotener Pfad: Route, die keinesfalls gewaehlt werden darf.
- Antwortvertrag: was die sichtbare Antwort leisten muss.
- Safety/Authority-Vertrag: welche Quellen, Ziele, Guardrails oder User-Bestaetigungen bindend sind.
- Latenzklasse: grobe akzeptable Zeitklasse fuer diesen Prompt.
- Regressionen: Prompts, die durch den Fix nicht schlechter werden duerfen.

Ohne diese Matrix nur Analyse, keine Code-Aenderung.

## Problemklasse Vor Fix-Ort

Codex muss vor jedem Fix zuerst die Problemklasse bestimmen. Der sichtbare kaputte Ast ist nicht automatisch der richtige Fix-Ort.

Beispiele:

- Nicht `SSH/Home Assistant`, sondern `Public Current Fact kollidiert mit lokal konfigurierter Connection-Action`.
- Nicht `Apple Watch`, sondern `Current-Fact Source Planning erzwingt ein blindes Jahr und blockiert offizielle Quellen`.
- Nicht `Button-Text`, sondern `Consent-Contract ohne sichtbare konkrete Operation`.
- Nicht `5 von 14`, sondern `Fleet Scope Authority wurde von config-bound/full-kind zu LLM-Sample verengt`.

Pflichtfragen vor Fix-Ort:

1. Ist der Fehler eine Instanz eines generischen Contract-Problems?
2. Welche anderen Connection-Kinds, Capabilities oder Surfaces koennen denselben Fehler zeigen?
3. Welche zukuenftigen modularen Connections wuerden durch einen Sonderfall nicht geschuetzt?
4. Welche generische Contract-Grenze besitzt die Entscheidung?
5. Welche Gegenbeispiele muessen weiter erlaubt bleiben?

Wenn Codex nur einen konkreten Prompt oder eine konkrete Connection-Art benennen kann, ist die Analyse noch nicht fertig.

## Build-Regel

Ein interner Build ist erst erlaubt, wenn:

- die relevanten roten Regressionstests vor dem Fix existierten oder der fehlende Testgrund dokumentiert ist,
- die neue Abnahmematrix gruen ist,
- die relevante Nachbarsuite gruen ist,
- die volle Suite gruen ist oder jede Abweichung explizit als fremder/offener Zustand belegt ist,
- `git diff --check` gruen ist,
- Codex die Restunsicherheiten vor dem Build offen nennt.

Fokusgruen allein reicht nie fuer einen Build.

## Keine Produktbehauptung Ohne Beleg

Codex darf nicht sagen:

- "Damit ist ARIA besser."
- "Das loest das Problem."
- "Das ist der richtige Layer."
- "Jetzt passt es."

Zulaessig ist nur eine belegte Aussage:

- "Dieser konkrete Pfad ist durch diese Tests abgesichert."
- "Dieser verbotene Pfad wird durch diesen Test blockiert."
- "Diese Restunsicherheit ist nicht abgedeckt."

## Routing-Vertraege

### Public Current Fact

Beispiele:

- `welches ist die neuste apple watch ultra`
- `was ist das neueste iPhone`
- `welche Version ist aktuell bei Home Assistant`
- `was ist die aktuelle Qdrant Version`

Erwarteter Pfad:

- Web/Public Source.
- Keine lokale Runtime-Action.
- Keine SSH-, SFTP-, SMB-, HTTP-API-, MQTT-, Mail- oder Discord-Action.
- Source-bound Antwort mit sichtbarer belastbarer Quelle oder ehrliches fail-closed.

Verbotener Pfad:

- Lokale Connections-Suche als alleinige Quelle.
- SSH auf einen aehnlich benannten Host, nur weil eine konfigurierte Connection existiert.
- RSS/Feed-Action, sofern der User keine konkrete Feed-/News-Quelle verlangt.
- Antwort aus Modellwissen ohne aktuelle Quelle.

Besonderheit:

- Das aktuelle Kalenderjahr darf nicht blind als Suchbegriff erzwungen werden. "Aktuell im Jahr 2026" bedeutet nicht, dass die offizielle Quelle "2026" enthalten muss.

### Local Instance Fact

Beispiele:

- `welche Version laeuft auf ubnsrv-homeassistant`
- `welche Home Assistant Version laeuft auf meiner lokalen Instanz`
- `pruefe auf ubnsrv-homeassistant die Home Assistant Version`

Erwarteter Pfad:

- Runtime-Action darf geplant werden, wenn ein exaktes konfiguriertes Ziel oder eine klare lokale Instanzautoritaet vorliegt.
- SSH/API/Website/andere Runtime nur gemaess vorhandener Guardrails.
- Mutierende oder unklare Befehle bleiben blockiert oder pending.
- Sichtbarer Preflight muss Ziel, Capability und konkrete Operation zeigen.

Verbotener Pfad:

- Automatische lokale Runtime-Action fuer eine oeffentliche Versionsfrage ohne lokalen Zielbezug.

### Explicit Feed/News Read

Beispiele:

- `lies mac-i-neueste-meldungen zu Home Assistant`
- `was gibt es auf heise-online-news zu Apple Watch`

Erwarteter Pfad:

- RSS/Feed-Read darf geplant werden, wenn der User die Feed-/News-Quelle explizit nennt oder eindeutig nach dieser Quelle fragt.
- Read-only Feed-Reads sollen keine unklare "Aktion ausfuehren"-UI ohne sichtbare Details erzeugen.

Verbotener Pfad:

- Feed-Read als Ersatz fuer allgemeine public current facts ohne explizite Feed-Quelle.

### SSH Target Authority

Beispiele:

- `Pruefe den Status von dev-node-02`
- `Pruefe den Status von srv-dev02`
- `Welche SSH-Ziele kennst du?`

Erwarteter Pfad:

- Exakte konfigurierte SSH-Refs duerfen gebunden werden.
- Unbekannte ref-like Targets muessen fail-closed/clarify sein.
- Aehnlich klingende Geschwister duerfen nicht automatisch gewaehlt werden.

Verbotener Pfad:

- `dev-node-02` auf `srv-dev02` oder irgendein semantisch nahes Profil mappen, wenn `dev-node-02` nicht konfiguriert ist.

### Fleet Scope Authority

Beispiele:

- `Wie fit sind meine Server?`
- `Pruefe Uptime, Root-Disk und RAM auf allen SSH-Zielen`

Erwarteter Pfad:

- Bei "alle SSH-Ziele"/vollstaendiger Servergruppe muss die Scope-Autoritaet config-bound/full-kind sein.
- Teilmengen muessen als Teilmengen sichtbar bleiben.
- Ergebnis darf nicht "alle" behaupten, wenn nur ein Teil geprueft wurde.

Verbotener Pfad:

- LLM-Top-K oder semantische Samples als vollstaendige Serverflotte ausgeben.
- Teilresultate in der Zusammenfassung zu "alle Server" aufblasen.

### Confirmation / Consent

Eine Bestaetigung ist nur gueltig, wenn die sichtbare UI vor dem Button mindestens enthaelt:

- Capability/Tool,
- Ziel(e),
- konkrete Operation, Query, Command, Path, Topic oder Message,
- Safety-/Policy-Grund, falls relevant.

Verboten:

- Button `Aktion ausfuehren` ohne sichtbare konkrete Aktion.
- Widerspruch wie "ARIA wuerde diese Aktion ohne weitere Rueckfrage freigeben" plus "requires preflight".
- Verstecken der konkreten Operation nur in Debug-Details.

Wenn diese Daten fehlen, darf kein bestaetigbarer Pending-State entstehen. ARIA muss blockieren oder nach fehlenden Details fragen.

## Latenzklassen

Diese Klassen sind keine harten Millisekunden-SLAs, sondern Abnahme-Hinweise:

- Simple public current fact mit offizieller Quelle: Ziel < 10s, Warnung ab 15s, inakzeptabel ab 25s ohne guten Grund.
- Source-bound Web-Recherche mit mehreren Quellen: Ziel < 20s, Warnung ab 30s.
- Runtime-Action mit Remote-IO: abhaengig von Zielanzahl; Antwort muss Zwischen-/Scope-Daten ehrlich zeigen.
- Fail-closed ohne Quellen: sollte schneller sein als erfolgreiche tiefe Recherche; ein 25s Fail-closed fuer simple facts ist ein Qualitaetsproblem.

Wenn ein Prompt die Latenzklasse reisst, ist das ein eigener Befund und darf nicht als "funktional korrekt" abgehakt werden.

## Standard-Abnahmematrix

Diese Matrix muss bei Routing-/Web-/Action-Fixes mindestens geprueft oder bewusst begruendet ausgenommen werden.

| Prompt | Erwarteter Pfad | Verbotener Pfad | Antwortvertrag |
| --- | --- | --- | --- |
| `welches ist die neuste apple watch ultra` | Web/Public Source | SSH/RSS/lokale Connections/model-only | Offizielle/geeignete Quelle oder ehrliches fail-closed; kein blinder Jahreszahl-Zwang |
| `welche ist die aktuellste Apple Watch Ultra` | Web/Public Source oder Wiederverwendung belegter Source Authority | Fail-closed trotz direkt vorher belegter offizieller Quelle | Konsistent mit belegter Quelle |
| `was ist das neueste iPhone` | Web/Public Source | Geruechte, lokale Actions, fail-closed wegen blindem Jahr | Offizielle Apple-Quelle oder ehrliches Quellenproblem |
| `welche Version ist aktuell bei Home Assistant` | Web/Public Release Source oder Rueckfrage public vs lokale Instanz | SSH auf `ubnsrv-homeassistant` ohne lokalen Zielbezug | Keine lokale Runtime-Action ohne explizite lokale Instanz |
| `welche Version laeuft auf ubnsrv-homeassistant` | Lokale Runtime darf geplant werden | Public-Web-Antwort als lokale Instanzversion | Ziel/Command/Policy sichtbar; Guardrail bindend |
| `lies mac-i-neueste-meldungen zu Home Assistant Version` | RSS read | Web-Rewrite, unsichtbarer Pending-Button | Feed + Query sichtbar |
| `Pruefe den Status von dev-node-02` | Missing/clarify, wenn nicht konfiguriert | Mapping auf `srv-dev02` oder anderes Geschwister | Keine Ausfuehrung auf falschem Ziel |
| `Pruefe den Status von srv-dev02` | Exaktes SSH-Ziel, policy-bound | Fleet-Ausweitung | Sichtbarer Preflight/Policy gemaess Action-Vertrag |
| `Welche SSH-Ziele kennst du?` | Connections inventory, config-bound | Freier Chat "keine Ziele" | Liste aus konfigurierten SSH-Zielen |
| `Wie fit sind meine Server?` | Full-kind SSH-Fleet, wenn Servergruppe vollstaendig autorisiert | LLM-Sample als alle Server | Scope und Anzahl ehrlich |
| `Pruefe Uptime, Root-Disk und RAM auf allen SSH-Zielen` | Full-kind SSH-Fleet | Teilmenge ohne Kennzeichnung | Anzahl geplant/geprueft sichtbar |
| `welcher interne ARIA Build ist aktuell` | ARIA release/update metadata, nicht Server-SSH | SSH auf beliebigen Host | Lokale Release-Meta oder klare Quelle |

## Owner-Spezifischer Operationsvertrag

Nach der Qdrant-gestuetzten Owner-/Operationsauswahl darf der zweite
Modellentscheid nur den Vertrag des gewaehlten Moduls sehen.

- Chat: aktuelle Nachricht, Sprache und begrenzter sichtbarer Chatkontext.
- Recipes: aktuelle Nachricht, Sprache und kompakte angebotene Recipe-IDs.
- Connections: aktuelle Nachricht, Sprache, Qdrant-Connection-Kandidaten und
  konfigurierte Kind-Anzahlen, aber keine vollstaendige Ref-Liste.
- Commands: dieselben begrenzten Connection-Daten, relevanter sichtbarer
  Folgekontext und nur die Action-Vertraege, deren exakte IDs aus aktuellen
  Qdrant-Kandidaten stammen.

Verboten sind globale World-Maps fuer diese Owner, Config-Scans als Ersatz fuer
fehlende oder stale Qdrant-Projektionen und das Kompilieren einer nicht
angebotenen Action-ID. Nach erfolgreicher Auswahl liefert die moduleigene
Source Authority weiterhin das vollstaendige Inventar oder die Runtime-Ziele;
Qdrant-Top-k bestimmt niemals Vollstaendigkeit.

Freie Felder wie `reason` und `confidence` bleiben Diagnostik. Ihr Fehlen oder
Format darf keinen ansonsten gueltigen Owner-/Operationsvertrag blockieren.

## Stop-Regeln

Codex muss ungepruefte Produktkorrekturen und Builds stoppen und zuerst die Evidence klaeren, wenn:

- ein Live-Export denselben Problemtyp nach einem Fix wieder schlechter zeigt,
- ein Fix einen verbotenen Pfad in der Matrix ermoeglicht,
- eine Abnahmematrix nicht reproduzierbar geprueft werden kann,
- die volle Suite oder eine relevante Nachbarsuite rot ist,
- der Fix mehrere Problemklassen gleichzeitig beruehrt und keine getrennte Risikoanalyse existiert.

Unter einer gueltigen CODE-Freigabe folgen autonom Postmortem, Ursachenanalyse, Akzeptanzmatrix und danach belegte Korrektur/Tests im erlaubten Scope. Dafuer keine separate Postmortem-, Fix-Design- oder CODE-NACH-POSTMORTEM-Freigabe verlangen. Ohne CODE bleibt die Arbeit lesend; normale `FREIGABE: CODE` genuegt zum Fortsetzen. Fehlende Evidence oder verbotener Zugriff bleiben echte Grenzen; BUILD bleibt separat und braucht gruene Gates.

## Risikoanalyse Vor Fix

Jeder Fixvorschlag muss vor Code diese Fragen beantworten:

1. Welche konkrete Live-Zeile oder welcher Test belegt den Fehler?
2. Welcher Layer besitzt die Entscheidung?
3. Welche vorgelagerten Layer koennen den Fix umgehen?
4. Welche nachgelagerten Layer koennen trotz Fix falsch antworten?
5. Welche Prompts koennen dadurch schlechter werden?
6. Welcher Test verhindert genau diese Verschlechterung?
7. Welche Latenz-Auswirkung ist zu erwarten?

Wenn Codex diese Fragen nicht beantworten kann, ist die korrekte Ausgabe: "unklar, keine Code-Aenderung".

## Dokumentationspflicht Nach Fix

Nach einem akzeptierten Fix muessen dokumentiert werden:

- welche Matrixzeilen abgedeckt sind,
- welche Tests diese Abdeckung leisten,
- welche Restunsicherheiten bleiben,
- ob ein Build sinnvoll ist oder nicht.

Build-Doku darf erst nach echtem Build/Export echte Image-/TAR-Daten behaupten.

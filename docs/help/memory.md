# ARIA Hilfe: Memory und Stores

Stand: 2026-07-09

## Zweck

Memory ist ARIAs semantischer Wissensspeicher. Es ist getrennt von Notizen, Logs und reinen Runtime-Ergebnissen.

ARIA nutzt Memory fuer:

- stabile Fakten ueber Nutzer und Umgebung
- Praeferenzen
- Session-Kontext
- Rollups ueber laengere Zeitraeume
- Dokument-RAG
- Experience Memory fuer sichere gelernte Aktionsmuster

## Was bewusst nicht automatisch ins Memory geht

- jede fluechtige Frage
- komplette SSH-/SMB-/RSS-Momentaufnahmen
- technische Logs ohne dauerhaften Wert
- mutierende Aktionsvorschlaege ohne Review

Das reduziert Memory-Rauschen und verhindert, dass ARIA aus zufaelligen Einmalereignissen dauerhafte Annahmen baut.

## Store-Typen

### Fakten und Praeferenzen

Langfristiges Wissen, das ARIA spaeter wiederverwenden darf.

### Session-Kontext

Arbeitsgedaechtnis fuer laufende Aufgaben und fruehere Turns.

### Rollups

Verdichtete Wochen-/Monats- oder Arbeitskontexte. Rollups helfen, ohne alle alten Chatdetails in jeden Prompt zu ziehen.

### Dokument-Collections

RAG-v1 fuer Uploads unter `/memories`. Unterstuetzt sind Text, Markdown und PDFs mit eingebettetem Text. OCR/Scan-PDFs sind nicht Teil von v1.

### Experience Memory

Erfolgreiche sichere Recipe-/Guardrail-/Action-Muster koennen als Planner-Kontext gespeichert werden. Sie helfen ARIA beim Vorschlagen, ersetzen aber nicht Policy oder Guardrails.

## Recall

Recall kombiniert je nach Anfrage:

1. direkte Fakten/Praeferenzen
2. Session-Kontext
3. Rollups
4. Dokument-Guides und passende Chunks
5. Experience Memory fuer Aktionsplanung

Chat-Details zeigen Quellen, Collection und Chunk-Referenzen, wenn Dokument-Recall genutzt wurde.

## UI

- `/memories` fuer den grafischen Gedaechtnis-Browser
- `/memories/import` fuer neue Dokumente und Memory-Importe
- `/memories/auto-memory` fuer Auto-Memory und agentisches Lernen
- `/memories/maintenance` fuer technische Pflege, Rebuilds und interne Lernartefakte
- `/config/embeddings` fuer Embedding-Modell und Sicherheitsabfrage bei vorhandenem Memory

### Auto-Memory und Lernen

Auto-Memory kann dauerhafte Fakten und Praeferenzen speichern, wenn ARIA genug Sicherheit hat. Agentisches Lernen kann ausserdem reviewbare Konventionen aus User-Feedback und erfolgreichen sicheren Laeufen extrahieren. Lernartefakte sind Kontext und Review-Material; sie umgehen keine Policy, Guardrails oder Bestaetigungen.

Der Learning Governor begrenzt neue Events, Candidates und Evals pro Quelle und Tag/Session nach FIFO. Inhalts-Fingerprints verhindern gleiche Candidate-/Eval-Inhalte auch dann, wenn Event- oder Candidate-IDs wechseln. Evals werden nur gespeichert, wenn die LLM sie als review-wuerdig einstuft und ihre Wichtigkeit den konfigurierten Mindestwert erreicht.

Im Browser bleiben alle vorhandenen Punkte ohne versteckte Filter sichtbar. `aktiv wirksam` bezeichnet explizit aktivierte Learning Hints, `nur Review` bezeichnet Candidates und `nur Audit` bezeichnet Events/Evals. ARIA bereinigt die internen Event-, Candidate- und Eval-Sammlungen automatisch beim Start und nach neuen Learning-Eintraegen. Die Retention behaelt pro Learning-Sammlung die wichtigsten und quellen-diversen Punkte; manuell reviewte/vorbereitete, aktivierte, promotete, regression-gepruefte oder explizit geschuetzte Punkte bleiben erhalten. Das Alter entscheidet nicht ueber das Behalten.

Die Auto-Memory-Seite listet alle Learning Events, Candidates, Evals und aktiven Hinweise des aktuellen Users vollstaendig auf. Eintraege koennen aufgeklappt, anhand ihrer Wirkung, Quelle, Wichtigkeit und ihres Synthesezustands geprueft und einzeln geloescht werden. Das Loeschen betrifft nur den ausgewaehlten Learning-Punkt.

Die Zusammenfassung trennt `Review-Warteschlange` von `Roh-Evidenz`. Alle Punkte bleiben sichtbar, aber nur kanonische, durch `learning_synthesis` aus mindestens zwei echten Quellpunkten verdichtete Candidates werden zur menschlichen Review-Aufgabe und erhalten Aktionsbuttons. Roh-Candidates bleiben als automatische Synthese-Evidenz sichtbar und einzeln loeschbar; sie muessen nicht manuell akzeptiert werden.

Review-Kandidaten werden direkt in ihrem aufgeklappten Eintrag geprueft. `Akzeptieren` markiert den Kandidaten als menschlich geprueft und fuehrt das Promotion Gate aus; es aktiviert noch nichts. `Ablehnen` schliesst ihn von einer Promotion aus. Nur geeignete Low-Risk-Kandidaten werden `eligible` und koennen mit `Apply vorbereiten` in die weiterhin inaktive Pruefstufe wechseln. `Gate & Regression` oeffnet die Detailpruefung fuer Regression, Preflight und die abschliessende explizite Aktivierung als schwachen Learning Hint. Nicht geeignete Typen bleiben sichtbar als `reviewed_blocked`.

Die automatische Learning-Synthese verdichtet zusammengehoerige, review-wuerdige Candidates zu wenigen kanonischen Review-Kandidaten. Sie bewahrt die Quell-IDs und Quellauszuege, ersetzt Roh-Candidates erst nach erfolgreichem Speichern und aktiviert nichts automatisch. Ueber `Jetzt synthetisieren` kann ein Admin denselben begrenzten Lauf manuell anstossen; ansonsten laeuft er beim Start.

Explizit aktivierte Learning Hints werden als schwache Signale in den bevorzugten LLM-first Turn-Plan geladen. Sie koennen weder Safety, Konfiguration, explizite Ziele noch belegte Quellen ueberstimmen. ARIA unterscheidet einen semantischen Treffer von einer tatsaechlichen Nutzung und zaehlt beides getrennt. Zeitnahes User-Feedback wird nur an wirklich benutzte Hinweise gebunden; wiederholt negatives Feedback suspendiert den Hinweis automatisch.

Explizit bestaetigte Schreibweisen koennen als strukturierter Entity-Alias gelernt werden, zum Beispiel `"Simpoini" bedeutet "Simponi 50 mg"`. Ein einzelner Tippfehler reicht nicht. Vor einer Aktivierung muss die kanonische Form in einem vorhandenen, nicht zu `aria_learning_*` gehoerenden Memory-Punkt exakt belegbar sein. Review und Aktivierung zeigen beobachtete Form, kanonische Form und Quell-Memory; der aktive Hint hilft der LLM nur bei der Kontextauflösung und darf Fakten, Dosierung oder den aktuellen User-Auftrag nicht veraendern.

Explizite dauerhafte User-Aussagen werden als strukturierte persönliche Claims mit Typ, Scope, Autorität und Status gespeichert. Nur aktive Claims gehen in den kleinen persönlichen Turn-Kontext; ersetzte, suspendierte oder strittige Claims bleiben sichtbar, wirken aber nicht normal. Rohe Learning Events, Candidates und Evals sind kein normaler Antwortkontext.

Der Bereich `Persönliches Modell` auf `/memories/auto-memory` zeigt aktuelle und historische Claims sowie getrennte Zähler für Bereitstellung, echte LLM-geprüfte Nutzung, geänderte Outcomes und Feedback. Claims können dort suspendiert, konfliktgeprüft reaktiviert oder punktgenau gelöscht werden. Der aktuelle User-Auftrag, Safety, Konfiguration, explizite Ziele und belegte Quellen bleiben immer stärker als der persönliche Kontext.

Zeitlich begrenzte Claims verwalten sich selbst: Zukünftige Angaben erscheinen als `geplant`, aktuell gültige als `wirksam`, und nach `Gültig bis` als `abgelaufen`. Geplante und abgelaufene Claims bleiben zur Kontrolle sichtbar, beeinflussen ARIA aber nicht.

Eine Korrektur erzeugt eine neue aktuelle Version und bewahrt den bisherigen Claim als Historie. Ziele und Projekte können pausiert, fortgesetzt, abgeschlossen und wieder geöffnet werden. Angaben mit Session-Scope bleiben in der vorhandenen Session-Memory-Schicht und werden nicht zu dauerhafter persönlicher Wahrheit.

Passen mehr als zwölf wirksame Claims in das persönliche Modell, wählt die LLM turnbezogen die relevanten Claims für die begrenzte Capsule. Ein erreichtes `Review ab` wird sichtbar markiert, deaktiviert den Claim aber nicht automatisch.

`/memories/auto-memory` zeigt das vollstaendige ungefilterte Inventar in drei Arbeitsbereichen: kanonische Kandidaten `Zu pruefen`, aktive oder suspendierte Hinweise und `Roh-Evidenz & Audit`. Bei aktiven Hinweisen zeigt die Seite Status, Version, Treffer, Nutzungen, positives/negatives Feedback und letzte Nutzung. Der User kann jeden Hinweis suspendieren, reaktivieren oder endgueltig loeschen. Zurueckgestellte Roh-Evidenz wird begrenzt erneut betrachtet, sobald neue Evidenz eintrifft.

### Gedaechtnis-Browser

Der Gedaechtnis-Browser ist die grafische Pflege- und Debug-Ansicht fuer ARIAs Qdrant-/Memory-Daten. Er zeigt dieselben Daten in zwei zusammenhaengenden Formen:

- Der Graph zeigt Root, Memory-Typen, Collections, Dokumente, Entries und Chunks als navigierbare Struktur.
- Der Inspector zeigt zur aktuellen Ebene die passenden Details und kann wie eine eigene Navigation genutzt werden.
- Auf der Eintrittsseite ist nichts ausgewaehlt; der Inspector zeigt alle Collections.
- Collection-Ebenen zeigen zuerst darunterliegende Dokumente oder Entries. Erst eine Ebene tiefer werden die zugehoerigen Chunks sichtbar.
- Dokument-Collections zeigen Dokumente und danach deren Chunks. Andere Collections zeigen Entries und deren Memory-Punkte.
- Einzelne Chunks, Points und Dokumente koennen im Browser geloescht werden. Inhalte werden bewusst nicht inline editiert, weil Aenderungen ein Re-Embedding brauchen; sicherer ist loeschen und neu erfassen.

### Struktur und semantische Naehe

Der Strukturmodus ist die Standardansicht. Er nutzt Zoom, freies Pan, Panbars, Fullscreen, Inspector-Drilldown und gespeicherte Struktur-Optionen fuer Abstand, Cluster und Anziehung.

Semantische Naehe erscheint erst auf konkreten Chunk-/Entry-/Point-Ebenen. Dann zeigt der Browser berechnete Nachbarschaften aus Qdrant-Embeddings, ohne Roh-Vektoren an den Browser auszuliefern.

Sichtbar sind nur sichere Metadaten, Textauszuege, Collection, Point-ID und berechnete Kanten. Fullscreen und iOS-/Touch-Bedienung nutzen dieselbe Logik wie der normale Browser.

## Embedding-Fingerprint

Memory- und Dokumenteintraege tragen einen Embedding-Fingerprint. Dadurch mischt ARIA alte und neue Embedding-Generationen nicht still waehrend Recall oder Dokument-Routing.

## Vergessen

Eintraege koennen direkt in `/memories` geloescht werden. Im Chat kann ARIA explizite Vergessenswuensche erkennen, sollte aber bei destruktiven Operationen bestaetigen.

## Warum Antworten manchmal duenn wirken

- Memory ist deaktiviert oder Qdrant nicht erreichbar
- Embedding-Modell wurde gewechselt und alte Eintraege passen nicht mehr
- zu wenige oder falsche Erinnerungen existieren
- die Anfrage ist eher ein Action-Prompt und wird vor RAG in den Agentic Action Flow geleitet
- Top-K oder Recall-Grenzen sind zu konservativ

## Test-Hinweise

- `merk dir ...` fuer explizites Speichern
- spaeter nach demselben Fakt fragen
- `/stats` und Chat-Details fuer Recall-Quellen pruefen
- `/memories` fuer Collection-/Dokument-/Chunk-Struktur und semantische Naehe pruefen

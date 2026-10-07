# Status-Map alpha664

## Gesamtstatus

- **Git-Stand:** `HEAD` ist der bereinigte oeffentliche alpha604-Commit.
- **Working Tree:** uncommitted alpha664-Refactor mit umfangreichen Aenderungen.
- **Public:** alpha604 bleibt der oeffentliche Release-Stand.
- **Intern:** alpha664 wurde technisch gebaut, aber fachlich nicht akzeptiert.
- **Teststatus:** Die automatisierte Suite war zuletzt gruen, ist aber kein Beleg
  fuer funktionierende End-to-End-Intelligenz.
- **Live-Status:** Der alpha664-Live-Lauf zeigt funktionierende Teilpfade und
  gravierende Regressionen.

Kein Teil dieser Map autorisiert einen Public Push oder die Veraenderung von
Qdrant-/Userdaten.

## Turn-Decision

### Done

- `turn_decision_v3` mit expliziten Decision-Kinds ist vorhanden.
- Actions, Context, Answer und Clarify werden strukturell getrennt.
- Contract-Normalisierung und vollstaendige Fehlercodes existieren.
- Ein begrenzter LLM-Repair ist implementiert.
- Unbekannte Actions und inkohaerente Action-Inputs werden fail-closed behandelt.

### In progress

- Fehler muessen nach Answer, Context, Clarify und Action differenziert behandelt
  werden.
- Repair und Degradation muessen fachlich statt nur strukturell bewertet werden.
- Token- und Latenzbudget des Decision-/Repair-Pfads ist nicht ausreichend
  stabilisiert.

### Known broken

- Viele Turns enden mit `invalid_turn_decision` und dem generischen
  Aktionsvertrag-Text.
- Harmlose Chat- und Context-Turns koennen dadurch hart abbrechen.
- Es gibt keinen iterativen Replan nach einem Tool- oder Context-Resultat.

## Turn Semantics

### Done

- Ein einheitlicher `turn_semantics_v1`-Contract ist vorhanden.
- Learning-Lanes und explizites Personal-Memory werden strukturiert markiert.
- Personal-Memory-Capture wird ohne passende Semantik entfernt.

### In progress

- Die Abstimmung zwischen Semantics, Decision-Kind und Action muss mit einer
  breiten Live-Matrix belegt werden.
- Semantische Unsicherheit braucht eine bessere Clarify-Strategie.

### Known broken

- Strikte Cross-Field-Validierung kann einen inhaltlich verstaendlichen Turn als
  insgesamt ungueltig verwerfen.
- Die Semantik ist eine Einmal-Klassifikation, kein lernender oder iterativer
  Planungsprozess.

## Meta-Catalog-Routing

### Done

- `meta_catalog_routing.py` ist der zentrale bounded Turn-Decision-Owner.
- Rollen-/Config-Menues begrenzen erlaubte Actions.
- Qdrant-Meta-Catalog, Document-Metadaten und exakte Connection-Treffer liefern
  Kandidaten.
- Sichtbarer Verlauf und letzter Turn-Frame koennen in die Decision einfliessen.
- Legacy Keyword-/Lexicon-Router wurden aus dem produktiven Pfad entfernt.

### In progress

- Kandidatenqualitaet, World-Map-Groesse und Kontextselektion muessen weiter
  kalibriert werden.
- Follow-ups muessen ohne separate Legacy-Rewrite-Schicht stabil funktionieren.
- Fehlende oder leere Catalog-Treffer brauchen eine fachlich sinnvolle
  Degradation.

### Known broken

- Allgemeine Chatfragen koennen als ungueltiger Aktionsvertrag abbrechen.
- Unbekannte Targets erhalten keinen hilfreichen Options- oder Clarify-Dialog.
- Der Router ist kein nativer Tool-Calling-Agent und kann Tool-Resultate nicht im
  selben Entscheidungsloop beobachten.

## Personal Memory

### Done

- `personal_memory.py` bietet strukturierte Claims, Lifecycle und Qdrant-Persistenz.
- Explizites dauerhaftes Merken und spaeterer Recall haben im alpha664-Live-Lauf
  fuer einen temporaeren Testwert funktioniert.
- UI-Sichtbarkeit, Korrektur, Suspendierung und Loeschung wurden aufgebaut.
- `memory_recall_contract.py` vereinheitlicht technische Recall-Parameter.
- `answer_influence.py` kann Nutzung als Receipt erfassen.

### In progress

- Recall-Kosten und -Latenz sind weiterhin hoch.
- Claim-Konsolidierung, Dublettenvermeidung und Konfliktaufloesung brauchen weitere
  produktnahe Tests.
- Ob gespeicherte Claims Antworten verlaesslich und angemessen beeinflussen, ist
  noch nicht ausreichend belegt.

### Known broken

- Vor alpha664 gab es wiederholte Regressionen beim expliziten Merken und Recall.
- Ein funktionierender Einzeltest belegt noch keine robuste persoenliche
  Intelligenz.
- Die Wirkungskette vom Claim bis zur finalen Antwort ist nicht durchgehend
  fachlich abgenommen.

## Learning

### Done

- `learning_directive.py` definiert typisierte Capture-Lanes.
- `learning_governor.py` implementiert Quoten, Retention, Dedup und
  Review-Wuerdigkeit.
- `learning_synthesis.py` konsolidiert Rohartefakte zu kanonischen Kandidaten.
- Learning-Artefakte, Review-Status, aktive Hinweise und Audit-Spuren sind im UI
  sichtbar und manuell kontrollierbar.
- Auto-Retention begrenzt Warteschlangen automatisch.

### In progress

- Die Synthese muss relevante von nutzloser Evidenz dauerhaft besser trennen.
- Learning-Effektivitaet muss anhand spaeterer Antwortverbesserung gemessen werden,
  nicht nur anhand erzeugter Artefakte.
- Aktivierung, Nutzung, positives/negatives Feedback und Suspendierung sind noch
  nicht als geschlossener, fachlich akzeptierter Zyklus belegt.

### Known broken

- Es gibt keinen Nachweis, dass alpha664 durch die vorhandenen Learning-Artefakte
  insgesamt klueger antwortet.
- Roh-Evidenz und Reviews koennen Kosten erzeugen, ohne den Antwortpfad sichtbar zu
  verbessern.
- "Self-learning" ist deshalb aktuell teilweise Infrastruktur und Governance,
  nicht nachgewiesene autonome Kompetenzsteigerung.

## Actions und Connections

### Done

- Registrierte Actions, Input-Schemas, Guardrails und Bestaetigungen bleiben
  erhalten.
- Bekannte Webhook-Connections wurden im alpha664-Live-Lauf erkannt und korrekt
  bestaetigt.
- `action_confirmation_ledger.py` bietet atomaren Exactly-once-Consume fuer
  signierte Bestaetigungen.
- Unbekannte Action- oder Connection-Referenzen werden nicht ausgefuehrt.

### In progress

- Action-Ergebnisse sollten fuer eine echte agentische Weiterentscheidung wieder
  in einen Planner-/Agent-Kontext gelangen.
- Multi-Target-Aktionen benoetigen belastbare Zielabdeckung und Resultataggregation.
- Benutzertexte fuer unbekannte oder unvollstaendige Actions muessen konkret
  werden.

### Known broken

- "Sind meine Server fit?" erkannte im Live-Lauf 14 Server, pruefte aber keinen.
- Ein Disk-Check pruefte 14 Server, die Antwort behauptete jedoch ohne klaren
  Schwellwert, der Platz sei ausreichend.
- Unbekannte Webhook-Ziele enden im generischen Aktionsvertrag-Fehler statt in
  einer hilfreichen Liste oder Rueckfrage.
- Es gibt keinen Observe/Act/Replan-Loop ueber Action-Resultate.

## Websuche

### Done

- Websuche ist als registrierte Surface/Context-Route in die neue Decision-Schicht
  eingebunden.
- Source-Acquisition und Evidenzpruefung existieren als nachgelagerte technische
  Schichten.

### In progress

- Suchplanung, Domain-Anforderungen, Source-Ranking und Follow-up-Kontext muessen
  als zusammenhaengender Pfad stabilisiert werden.
- Latenz und Query-Vervielfachung muessen begrenzt werden.

### Known broken

- Offizielle Qdrant-Suchen scheiterten wiederholt mit
  `web_source_no_reliable_sources` beziehungsweise `site_query_target_miss`.
- Generierte Queries enthielten fehlerhafte `site:`-Targets.
- Web-Follow-ups lieferten teilweise irrelevante Quellen.
- Die Regression war beim Abbruch nicht behoben.

## Was beim Abbruch nicht fertig war

- Keine fachlich bestandene alpha664-End-to-End-Matrix.
- Kein Graceful-Degradation-Pfad fuer ungueltige Answer-/Context-Decisions.
- Keine belastbare Loesung fuer `invalid_turn_decision` bei normalen Turns.
- Keine funktionierende offizielle Websuche im geprueften Qdrant-Fall.
- Keine robuste Multi-Server-Fitness-Aktion.
- Keine akzeptierte Kalibrierung von Antwortbehauptungen gegen echte Resultate.
- Keine abgeschlossene Performance-/Token-Optimierung.
- Kein nativer iterativer Tool-Calling-Agent.
- Kein Nachweis, dass Learning die spaetere Antwortqualitaet messbar verbessert.
- Kein Commit des alpha664-Working-Trees.
- Kein interner oder oeffentlicher Release, der fachlich als Nachfolger von
  alpha604 akzeptiert wurde.

## Belegte Teilfunktion im letzten Live-Lauf

- Personal-Memory-Testwert speichern und wiederfinden: funktioniert.
- Exaktes Dokument zu Simpoini finden: funktioniert.
- Bekannten Webhook ausloesen und bestaetigen: funktioniert.
- Disk-Abfrage ueber 14 registrierte Server: Ausfuehrung funktioniert, Aussage
  nicht ausreichend kalibriert.

Diese Punkte duerfen nicht als Gesamtfreigabe interpretiert werden.

## Uebergabeprioritaet

1. Reproduzierbare Fixtures fuer die fehlgeschlagenen Live-Turns sichern.
2. Decision-Fehler nach Turn-Klasse trennen; Action-Safety nicht lockern.
3. Normalen Chat und Context mit Graceful Degradation stabilisieren.
4. Web-Source-Planung und Multi-Target-Resultatabdeckung reparieren.
5. Danach entscheiden, ob der bounded Single-Turn-Ansatz genuegt oder ein echter
   Tool-Calling-Loop eingefuehrt werden soll. Die historische Absicht dazu ist
   **ABSICHT UNBEKANNT**.

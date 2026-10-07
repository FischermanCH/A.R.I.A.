# Beabsichtigter Turn-Flow in alpha664

## Kurzfassung

Der neue Turn-Pfad soll aus einem registrierten Weltbild und dem aktuellen
Gespraech genau eine strukturierte Turn-Decision bilden. Diese Decision wird
semantisch und technisch validiert. Erst danach werden Kontext geladen, eine
Antwort erzeugt, eine Rueckfrage gestellt oder eine Aktion an die kontrollierte
Runtime uebergeben.

Der implementierte Pfad ist bounded-agentisch, aber nicht iterativ: Das
entscheidende LLM sieht vor der Decision den Prompt und Registry-Kontext, nicht
spaeter die Tool-Resultate, um daraus im selben Loop einen neuen Schritt zu planen.

## 1. Eingang des Benutzer-Prompts

Der Turn beginnt mit:

- aktuellem Benutzertext;
- Sprache und Benutzer-/Rollenidentitaet;
- sichtbarem Chat-Verlauf;
- optionalem `last_turn_frame` und pending action context;
- verfuegbaren Rollen-, Config- und Connection-Grenzen;
- optionalen Personal-Memory-Claims und reviewed learning hints.

Diese Daten sind Eingaben fuer die Turn-Entscheidung. Sie sollen nicht vorab durch
eine Wortliste auf einen Intent reduziert werden.

## 2. Aufbau des erlaubten Weltbilds

`meta_catalog_routing.py` baut ein kompaktes, deklaratives Weltbild auf. Es
kombiniert mehrere Quellen:

- die rollen- und konfigurationsgebundene `AriaTurnMenu` als Autoritaet fuer
  erlaubte Actions;
- die `SurfaceRegistry` und registrierte Context-Loader;
- Treffer aus der Meta-Catalog-Collection in Qdrant;
- benutzerspezifische Document-Meta-Catalog-Treffer;
- exakte Treffer aus aktuell konfigurierten Connections;
- Personal-Memory-Capsule und Learning-Hinweise, soweit fuer den Turn freigegeben.

Die allgemeine Qdrant-Collection heisst instanzbezogen
`aria_meta_catalog_<instance>`. Dokument-Metadaten koennen in separaten,
benutzerspezifischen `aria_document_meta_*`-Collections liegen.

### Rolle der Meta-Catalog-Registry

Die Registry macht semantisch auffindbar, was ARIA kennt und tun kann. Ein
Meta-Catalog-Dokument kann unter anderem enthalten:

- stabile IDs und Referenzen;
- Surface, Typ und Gruppe;
- Titel, Beschreibung, Aliase und Tags;
- angebotene Loader oder Executor;
- Action-Kandidaten;
- Risiko- und Bestaetigungsmetadaten.

Qdrant liefert Kandidaten und semantische Naehe. Es darf nicht eigenstaendig eine
Aktion autorisieren. Die tatsaechlich erlaubten Actions bleiben an Rolle,
Konfiguration und deklarierte Contracts gebunden. Exakte Connection-Treffer
ergaenzen den Index, damit frisch konfigurierte Verbindungen nicht erst nach einem
vollstaendigen Reindex sichtbar werden muessen.

## 3. `meta_catalog_routing`: eine begrenzte LLM-Entscheidung

Der Router uebergibt dem LLM ein kompaktes `llm_input_contract` mit:

- Prompt und relevantem sichtbarem Verlauf;
- erlaubten Surfaces und Actions;
- Meta-Catalog-Kandidaten;
- Context- und Target-Moeglichkeiten;
- pending action context und letztem Turn-Frame;
- Personal- und Learning-Kontext;
- dem erwarteten `turn_decision_v3`-Schema.

Das LLM soll ausschliesslich deklarierte IDs verwenden und eine Decision waehlen:

- `answer`: ohne weiteren Kontext direkt antworten;
- `context`: registrierten Kontext laden und daraus antworten;
- `action`: genau eine registrierte Aktion vorbereiten;
- `clarify`: eine notwendige Rueckfrage stellen.

Die erste Ausgabe ist ein Decision-Header. Action-Inputs werden bei Bedarf in
einem separaten, auf die bereits gewaehlte Action begrenzten LLM-Schritt erzeugt.
Dieser zweite Schritt darf die Action nicht wechseln.

## 4. `turn_semantics`: einheitliche semantische Lane

`turn_semantics.py` normalisiert die vom LLM deklarierte Turn-Semantik. Gueltige
Kategorien sind:

- `ordinary`;
- `explicit_personal_memory`;
- `behavior_feedback`;
- `personal_observation`;
- `entity_alias_candidate`;
- `procedure_or_recipe_candidate`;
- `runtime_outcome_review`.

Die Semantik hat drei Aufgaben:

1. Sie kennzeichnet besondere Learning-Lanes.
2. Sie autorisiert explizites Personal-Memory-Capture nur bei
   `explicit_personal_memory`.
3. Sie liefert eine pruefbare Bindung zwischen Bedeutung und gewaehlter Action.

Sie soll nicht aus freien Begriffen selbst eine beliebige Action waehlen.

## 5. `validate_turn_decision`: Contract-Grenze

`turn_decision_contract.py` prueft, ob Decision-Kind, Contract-Mode,
Answer-Mode, Context-Anforderungen, Personal-Resolution, Action und Action-Input
zusammenpassen.

Die Validierung soll verhindern, dass etwa:

- eine Answer-Decision gleichzeitig eine Action ausfuehrt;
- eine Action ohne registrierten Contract oder Input startet;
- eine Context-Decision keinen Kontext anfordert;
- ein Personal-Memory-Match auf nicht vorhandene Claims verweist;
- ein semantisch nicht autorisierter Memory-Capture ausgefuehrt wird.

Technische Normalisierung darf redundante Felder korrigieren, wenn die explizite
Decision eindeutig ist. Sie darf keine neue Bedeutung erfinden.

Alle Fehlercodes und der aktuelle Fehlerpfad stehen in
`02-turn-decision-contract.md`.

## 6. Ein Reparaturversuch

Ist der Decision-Header ungueltig, fordert `meta_catalog_routing.py` genau einen
vollstaendigen Ersatz vom LLM an. Es wird kein partieller Patch auf die erste
Decision angewendet.

Der Repair-Schritt soll:

- bei einem sicheren, bekannten Fall eine kohaerente Decision liefern;
- andernfalls auf `clarify` ohne Aktion wechseln;
- keine nicht registrierte Action erfinden.

Nach dem Repair wird erneut validiert. Ein weiterer autonomer Reparatur- oder
Replan-Loop existiert nicht.

## 7. Action-Input-Extraktion

Wenn genau eine gueltige Action ausgewaehlt wurde und ihr Input fehlt, erzeugt ein
separater LLM-Aufruf nur den Input fuer diese Action. Danach werden geprueft:

- passt der gemeldete Action-Name zur festgelegten Action;
- ist der Input ein Objekt;
- ist die Konfidenz ausreichend;
- sind Personal-Claim-IDs bekannt;
- sind Connection-Referenzen bekannt und erlaubt;
- erfuellt der Input das Action-Schema.

Erst dann darf der nachgelagerte Preflight beginnen.

## 8. Materialisierung der gueltigen Decision

Eine gueltige Decision wird zu einem `AriaTurnPlan` materialisiert:

- Context-Requests werden an registrierte Loader uebergeben.
- Replay-Anforderungen koennen den letzten Turn-Frame einbeziehen.
- Inventory- und Zielmodi werden technisch normalisiert.
- Action-Inputs werden an den deklarierten Action-Contract gebunden.

### Antwort

Bei `answer` wird direkt geantwortet. `response_text` darf nur zu einer
Answer-Decision gehoeren.

### Kontextantwort

Bei `context` werden die angeforderten Quellen geladen. Die Antwort soll aus der
gelieferten Evidenz entstehen und keine nicht belegten Runtime-Ergebnisse
behaupten.

### Rueckfrage

Bei `clarify` soll eine konkrete, benutzerfreundliche Frage gestellt werden, wenn
Ziel oder notwendige Angaben fehlen.

### Aktion

Bei `action` folgen Action-Contract, Guardrails, Risikoanalyse und gegebenenfalls
Bestaetigung. `action_confirmation_ledger.py` stellt fuer signierte
Bestaetigungen einen atomaren, einmaligen Consume-Pfad bereit. Danach fuehrt die
jeweilige Connection- oder Runtime-Schicht aus.

## 9. Resultat und Antwortbildung

Runtime-Resultate werden durch bestehende Result-Summarizer und Evidenzgrenzen in
eine Benutzerantwort ueberfuehrt. Learning- und Personal-Memory-Nutzung kann ueber
`answer_influence.py` als Receipt erfasst werden.

Ein echter Agent wuerde das Resultat wieder dem entscheidenden LLM geben und ihm
die Wahl des naechsten Tools oder des Abschlusses ueberlassen. Dieser Schritt ist
in alpha664 nicht vorhanden. Ob er innerhalb des alpha604-alpha664-Refactors
beabsichtigt, aber noch offen war, ist: **ABSICHT UNBEKANNT**.

## 10. Fehler- und Degradationspfad

Sicherheitsrelevante Action-Fehler sollen fail-closed enden: keine Ausfuehrung bei
unbekannter Action, falschem Ziel oder ungueltigem Input.

Aktuell enden jedoch auch andere nicht reparierbare Contract-Fehler im selben
generischen Text:

> Ich konnte keinen gueltigen Aktionsvertrag bilden. Es wurde nichts ausgefuehrt.

Damit wird der beabsichtigte End-to-End-Fluss fuer normale Chat- und Context-Turns
unterbrochen. Das ist ein bekannter alpha664-Defekt, kein erfolgreicher
Graceful-Degradation-Pfad.

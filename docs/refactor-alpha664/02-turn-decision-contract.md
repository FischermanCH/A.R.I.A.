# Turn-Decision-Contract und Fehlerverhalten

## Zweck

`turn_decision_contract.py` definiert `turn_decision_v3`. Die Validierung prueft
nicht, ob eine Antwort inhaltlich gut ist. Sie prueft, ob die strukturierte
Entscheidung in sich kohaerent, registriert und technisch ausfuehrbar ist.

Gueltige Decision-Kinds sind `answer`, `context`, `action` und `clarify`.

## Technische Normalisierung vor der Fehlerausgabe

Die Validierung kann zwei belegte Normalisierungen vornehmen:

- Ein redundanter, ungueltiger `contract_mode` kann aus einem gueltigen expliziten
  Decision-Kind abgeleitet werden.
- Bei Personal-Memory-Capture kann eine unpassende Personal-Resolution ohne
  selektierte Claims auf `not_applicable` normalisiert werden.

Diese Normalisierung soll widerspruechliche Darstellung bereinigen. Sie ersetzt
keine semantische Entscheidung.

## Vollstaendige Fehlerliste aus `validate_turn_decision`

Die folgende Liste umfasst jeden Error-Code, den die Funktion direkt erzeugen
kann.

| Error-Code | Bedeutung |
| --- | --- |
| `unknown_decision_kind` | Das Decision-Kind ist nicht `answer`, `context`, `action` oder `clarify`. |
| `unknown_action` | Mindestens eine angegebene Action ist nicht in der erlaubten Action-Menge. |
| `multiple_actions_require_composite_contract` | Mehrere Actions wurden angefordert, obwohl kein Composite-Contract existiert. |
| `unknown_contract_mode` | Der Contract-Mode ist unbekannt und konnte nicht sicher normalisiert werden. |
| `unknown_answer_mode` | Der Answer-Mode ist nicht Teil des erlaubten Contracts. |
| `personal_context_resolution_missing` | Fuer einen Turn mit Personal-Context-Anforderung fehlt die Resolution. |
| `unknown_personal_context_resolution` | Die Personal-Resolution ist kein erlaubter Wert. |
| `personal_context_resolution_reason_missing` | Fuer die Personal-Resolution fehlt die begruendende Kurzangabe. |
| `unknown_selected_personal_claim_id` | Die Decision verweist auf einen Claim, der nicht in den angebotenen Claim-IDs lag. |
| `personal_context_match_requires_selected_claim` | `matched` wurde gemeldet, aber kein Claim ausgewaehlt. |
| `personal_context_resolution_rejects_selected_claim` | Eine Resolution ohne Match enthaelt dennoch selektierte Claims. |
| `personal_context_no_hit_requires_complete_coverage` | `complete_no_hit` wurde behauptet, obwohl die Personal-Suche nicht vollstaendig war. |
| `personal_context_no_hit_must_answer_without_context` | Bei bestaetigtem No-Hit soll nicht weiter aus Personal Context geantwortet werden. |
| `personal_context_no_hit_requires_response` | Ein bestaetigter No-Hit enthaelt keine Benutzerantwort. |
| `personal_context_inconclusive_conflicts_with_complete_coverage` | `inconclusive` widerspricht einer als vollstaendig gemeldeten Suche. |
| `independent_personal_context_requires_context_decision` | `independent_context` ist ausserhalb einer Context-Decision unzulaessig. |
| `action_decision_requires_one_action` | Eine Action-Decision hat nicht genau eine Action. |
| `action_decision_requires_action_contract` | Eine Action-Decision verwendet nicht den Action-Contract-Mode. |
| `non_action_decision_with_action` | Eine Answer-, Context- oder Clarify-Decision enthaelt dennoch eine Action. |
| `answer_decision_contract_mismatch` | Answer-Decision und Contract-Mode passen nicht zusammen. |
| `answer_decision_cannot_load_context` | Eine direkte Answer-Decision fordert gleichzeitig Kontext. |
| `context_decision_requires_answer_contract` | Eine Context-Decision verwendet nicht den vorgesehenen Answer/Context-Contract. |
| `context_decision_requires_context` | Eine Context-Decision fordert keinen Kontext an. |
| `clarify_decision_contract_mismatch` | Clarify-Decision und Contract-Mode passen nicht zusammen. |
| `clarify_decision_cannot_load_context` | Eine Clarify-Decision fordert gleichzeitig Kontext. |
| `response_text_requires_answer_decision` | `response_text` wurde an eine Nicht-Answer-Decision gebunden. |
| `orphan_action_input` | Action-Input ist vorhanden, aber es gibt keine passende einzelne Action. |
| `missing_or_invalid_action_input:<action>` | Fuer die benannte Action fehlt ein schema-konformer Input. |
| `action_semantics_mismatch:<action>` | Die gewaehlte Action passt nicht zu den deklarierten Turn-Semantics. |
| `semantic_action_missing` | Die Semantik verlangt eine gebundene Action, aber keine passende Action ist vorhanden. |

## Zusaetzliche Fehler aus dem Routing-Pfad

Diese Codes stammen nicht direkt aus `validate_turn_decision`, werden aber in
`meta_catalog_routing.py` waehrend Repair und Action-Input-Extraktion an dieselbe
Fehlerkette angehaengt:

| Error-Code | Bedeutung |
| --- | --- |
| `repair_low_confidence` | Der einmalige Decision-Repair lag unter der erlaubten Konfidenz. |
| `action_input_action_mismatch` | Die Input-Extraktion meldete eine andere Action als die zuvor festgelegte. |
| `action_input_not_object` | Der extrahierte Action-Input war kein Objekt. |
| `action_input_low_confidence` | Die Input-Extraktion lag unter der Konfidenzgrenze. |
| `action_input_unknown_personal_claim_id` | Der Input referenziert einen nicht angebotenen Personal Claim. |
| `action_input_unknown_connection_ref` | Der Input referenziert eine nicht bekannte oder nicht erlaubte Connection. |
| `action_input_contract_missing` | Fuer die gewaehlte Action ist kein nutzbarer Input-Contract vorhanden. |

Anschliessend kann die finale Contract-Validierung weitere der oben gelisteten
Fehler hinzufuegen.

## Beabsichtigtes Verhalten bei einem Fehler

### Belegt und by design

Folgendes Verhalten ist durch Code und Tests belegt:

1. Eine ungueltige erste Decision wird nicht direkt ausgefuehrt.
2. Es gibt maximal einen LLM-Repair des gesamten Decision-Headers.
3. Eine Action-Input-Extraktion darf die bereits festgelegte Action nicht wechseln.
4. Nicht registrierte Actions, Claims oder Connections werden nicht akzeptiert.
5. Bleibt eine ausfuehrbare Action inkohaerent, wird nichts ausgefuehrt.
6. Nach dem fehlgeschlagenen Repair wird ein blockierter Clarify-Plan erzeugt.

Der harte Stopp ist deshalb fuer unsichere oder unvollstaendige Aktionen
**BY DESIGN**. Er ist eine Safety-Grenze.

### Known broken

Der aktuelle Implementierungsfehler liegt in der zu groben Behandlung aller
ungueltigen Decisions:

- Auch normale Chat- oder Context-Turns koennen im Action-Fehlertext enden.
- Die Meldung sagt immer, es habe kein gueltiger Aktionsvertrag gebildet werden
  koennen, selbst wenn der Benutzer keine Aktion wollte.
- Nach dem einen Repair gibt es keinen fallbezogenen Fallback auf eine sichere
  direkte Chat-Antwort.
- Es gibt keine strukturierte Auswahl-Rueckfrage mit den tatsaechlich moeglichen
  Optionen.
- Ein lokaler Contract-Widerspruch kann damit den gesamten Turn abbrechen, obwohl
  eine harmlose Antwort oder konkrete Rueckfrage moeglich waere.

Dieses Verhalten ist fuer normale Antwort- und Kontextfaelle **KNOWN BROKEN**.
Die alpha664-Live-Tests zeigen genau diesen Fehler bei allgemeinen Fragen und
unbekannten Targets.

### War die generische Meldung ein Platzhalter oder TODO?

Im untersuchten Code und in den zugehoerigen Tests gibt es keinen belegten TODO,
der die Meldung ausdruecklich als temporaeren Platzhalter kennzeichnet. Die Tests
schreiben fail-closed nach einem ungueltigen Repair fest.

Ob historisch fuer normale Chat-/Context-Fehler eine Graceful Degradation geplant
war, aber nicht mehr implementiert wurde, ist: **ABSICHT UNBEKANNT**.

Damit gilt:

- Action-Safety-Stopp: by design.
- Derselbe generische Stopp fuer jeden Decision-Fehler: known broken.
- Historischer Plan fuer einen Chat-Fallback oder Optionsdialog:
  **ABSICHT UNBEKANNT**.

## Erforderliche fachliche Trennung fuer die Weiterarbeit

Die naechste Implementierung sollte nicht einfach die Validierung lockern. Sie
sollte Fehler nach Turn-Klasse behandeln:

- **Action:** fail-closed; unbekanntes Ziel oder Input klar benennen; keine
  Ausfuehrung.
- **Clarify:** konkrete fehlende Angabe oder bekannte Optionen nennen.
- **Context:** bei unsicherem Context-Target rueckfragen oder sicher ohne diesen
  Kontext antworten, wenn die Antwort unabhaengig moeglich ist.
- **Answer:** einen reinen Darstellungswiderspruch reparieren oder eine sichere
  Chat-Antwort erlauben; niemals daraus heimlich eine Action machen.

Das ist eine Status-/Uebergabeempfehlung, keine Behauptung ueber bereits
implementiertes Verhalten.

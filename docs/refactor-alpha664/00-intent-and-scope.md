# Refactor alpha604 -> alpha664: Absicht und Umfang

## Ausgangslage

Diese Dokumentation beschreibt den uncommitted Refactor zwischen dem oeffentlichen
Git-Stand alpha604 (`HEAD`) und dem internen Working Tree alpha664. Sie beschreibt
Absicht und aktuellen Status. Sie ist keine Aussage, dass alpha664 fachlich
abgenommen oder releasefaehig ist.

Der alte Turn-Pfad verteilte freie Bedeutungsentscheidungen auf Wortlisten,
Regex-Muster, Scoring, Sonderfall-Router und nachgeschaltete Escape-Hatches. Ein
LLM konnte zwar eine Absicht klassifizieren, danach bestimmte jedoch ein
hartverdrahteter Trichter die weitere Ausfuehrung. Neue Faelle wurden haeufig durch
weitere Regeln ergaenzt. Dadurch entstanden mehrere konkurrierende Autoritaeten fuer
dieselbe Frage: Was will der Benutzer, welcher Kontext ist relevant und welche
Aktion soll ausgefuehrt werden?

## Was der Refactor erreichen sollte

Der Refactor sollte freie Bedeutung aus deterministischen Wortlisten und
Sonderfall-Routern herausloesen und einer begrenzten LLM-Entscheidung uebergeben.
Die neue Schicht sollte:

- den Benutzer-Prompt und den sichtbaren Chat-Kontext semantisch verstehen;
- nur tatsaechlich registrierte Surfaces, Collections und Actions sehen;
- genau eine strukturierte Turn-Decision erzeugen;
- Kontext, Antwort, Rueckfrage und Aktion klar unterscheiden;
- Aktionen nur ueber typisierte Inputs, Guardrails und Bestaetigungen ausfuehren;
- Persoenliches Memory und Learning als explizite, kontrollierte Pfade behandeln;
- bei unbekannten Zielen keine Aktion erfinden;
- technische Deterministik fuer Contracts, Safety, Validierung, Runtime und
  Observability behalten;
- fuer Endbenutzer natuerlicher und weniger von exakten Formulierungen abhaengig
  sein.

"Agentisch" bedeutet im implementierten alpha664-Stand eine begrenzte
LLM-Entscheidung innerhalb eines Turns. Es existiert kein nativer iterativer
Tool-Calling-Loop, in dem dasselbe LLM Tools aufruft, Resultate beobachtet und
daraufhin neu plant. Ob ein solcher Loop bereits Ziel dieses konkreten Refactors
war, ist: **ABSICHT UNBEKANNT**.

## Architekturprinzip

Die angestrebte Autoritaetskette lautet:

1. Registry und Konfiguration definieren, was existiert und erlaubt ist.
2. Das LLM entscheidet innerhalb dieser Grenzen ueber Bedeutung und Turn-Typ.
3. Strukturierte Contracts pruefen die Entscheidung technisch.
4. Guardrails, Bestaetigungen und Runtimes kontrollieren Ausfuehrungen.
5. Resultate und Evidenz begrenzen, was die Antwort behaupten darf.

Deterministik sollte damit nicht vollstaendig verschwinden. Sie sollte keine freie
Bedeutung mehr erraten, sondern deklarierte Grenzen durchsetzen.

## Warum die entfernten Module problematisch waren

### `capability_router.py`

Der Capability Router leitete Bedeutung, Capability, Ziel und teilweise Felder aus
Lexikon-Treffern ab. Damit konnte eine Wortwahl die technische Route staerker
bestimmen als der gesamte Satzkontext. Neue Produkte, Hosts und Formulierungen
erforderten neue Regeln; Mehrdeutigkeiten fuehrten zu Sonderfaellen.

### `routing_lexicon.py`

Dieses Modul machte die JSON-Wortlisten zu einer zentralen semantischen Autoritaet.
Die Listen waren leicht erweiterbar, aber ihre Gesamtauswirkung war schwer zu
ueberblicken. Ueberlappende Begriffe konnten mehrere Router beeinflussen.

### `turn_intent_arbitration.py`

Die Intent-Arbitration kombinierte Keyword-Routing, eine LLM-Klassifikation und
Legacy-Fallbacks. Dadurch war nicht eindeutig, welche Instanz am Ende den Turn
besass. Eine korrekte LLM-Deutung konnte spaeter von Legacy-Semantik ueberschrieben
werden.

### `action_planner_scoring.py`

Keyword- und Template-Scores waehlen Aktionen anhand lokaler Treffer. Das ist fuer
freie Sprache keine belastbare Bedeutungsentscheidung. Kleine Score-Aenderungen
konnten eine andere Aktion gewinnen lassen, ohne dass der Benutzerwunsch sich
geaendert hatte.

### `action_planner_followups.py`

Vorgefertigte Follow-up- und Zielphrasen kodierten erwartete Sprachmuster. Sie
konnten hilfreiche Vorschlaege liefern, wurden aber zu einer weiteren semantischen
Sonderautoritaet neben Chat-Historie und LLM.

### `chat_freshness.py`

Aktualitaetsbedarf wurde separat durch Phrasen und eine weitere Arbitration
ermittelt. Dadurch konnte Web-Freshness unabhaengig von der eigentlichen
Turn-Decision eine Route erzwingen oder verhindern.

### `context_evidence.py`

Lexikalische Evidenz- und Inventarfilter entschieden anhand von Begriffen, welcher
Kontext als passend gilt. Das vermischte semantische Relevanz mit technischer
Evidenzvalidierung und konnte passende Quellen verwerfen oder unpassende zulassen.

### `followup_resolution.py`

Follow-ups wurden vor dem eigentlichen Turn-Router separat durch Regex,
Historienheuristiken und einen weiteren LLM-Aufruf umgeschrieben. Damit existierte
erneut eine konkurrierende Deutung des Benutzerwunsches.

### `lexicons/*.json`

Die entfernten Wortlisten lieferten Begriffe, Stopwoerter, Extraktionsmuster,
Scoring-Gewichte und produktspezifische Formulierungen. Ihr gemeinsames Problem war
nicht JSON als Format, sondern ihre Rolle als Autoritaet fuer freie Bedeutung.
Einzelne technische Daten koennen weiterhin in strukturierten Registries oder
Schemas existieren; freie Sprache soll daraus aber nicht regelbasiert entschieden
werden.

## Was bewusst erhalten bleiben sollte

- deklarierte Actions und ihre Input-Schemas;
- rollen- und konfigurationsgebundene Menues;
- Connection-Runtimes und Secure-Store-Grenzen;
- Guardrails, Risiko- und Bestaetigungsregeln;
- Qdrant als Registry-, Kontext- und Memory-Speicher;
- strukturierte Validierung und Normalisierung;
- Result-Summarizer, Evidenzgrenzen und Observability;
- fail-closed fuer unbekannte oder unvollstaendige ausfuehrbare Aktionen.

## Nicht-Ziele und offene Grenzen

- Der Refactor ist kein Beleg fuer eine fertige allgemeine Agentenarchitektur.
- Der Refactor garantiert nicht, dass Learning ARIA bereits messbar klueger macht.
- Die vorhandenen Runtimes wurden nicht durch native LLM-Tools ersetzt; sie sind
  weiterhin nachgeschaltete Ausfuehrungssubstrate.
- Ein sicherer, iterativer Observe/Act/Replan-Loop ist nicht implementiert.
- Welche Alt-Komfortfunktionen bewusst entfallen durften, ist teilweise
  **ABSICHT UNBEKANNT**; Details stehen in `04-deleted-and-replaced.md`.

## Erfolgskriterium

Der Refactor waere fachlich erfolgreich, wenn normale Chat-Turns, Kontextfragen,
Follow-ups, Personal Memory, Websuche und bekannte Aktionen natuerlich
funktionieren, waehrend unbekannte oder riskante Aktionen kontrolliert stoppen.
alpha664 erfuellt dieses Kriterium aktuell nicht: Mehrere Turns brechen mit
`invalid_turn_decision` ab, obwohl keine unsichere Aktion ausgefuehrt werden sollte.

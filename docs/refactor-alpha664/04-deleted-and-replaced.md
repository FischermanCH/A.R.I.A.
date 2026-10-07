# Geloeschte Komponenten und ihr Ersatz

## Leseregel

"Ersetzt durch" bedeutet nicht automatisch Funktionsparitaet. Es bezeichnet die
neue vorgesehene Autoritaet oder den naechsten technischen Owner. Wo keine
belegbare Absicht vorliegt, steht ausdruecklich **ABSICHT UNBEKANNT**.

## Geloeschte Python-Module

| Geloeschte Komponente | Fruehere Rolle / Problem | Neuer Owner oder bewusste Entfernung | Status / Luecke |
| --- | --- | --- | --- |
| `aria/core/capability_router.py` | Lexikonbasierte Capability-, Target- und Feldableitung aus freier Sprache. | `AriaTurnMenu`, `SurfaceRegistry`, `meta_catalog_routing.py`, deklarierte Action-Schemas und Guardrails. | Semantische Entscheidung ersetzt; einige alte Komfort-Extraktionen haben keine direkte Paritaet. |
| `aria/core/routing_lexicon.py` | Loader und Zugriffsschicht fuer die zentrale Routing-Wortliste. | Meta-Catalog-Registry, strukturierte Config/Registries und erlaubte Menues. | Bewusst entfernt; keine neue freie Wortlistenautoritaet. |
| `aria/core/turn_intent_arbitration.py` | Keyword-Router, LLM-Intent und Legacy-Fallback konkurrierten um Turn Ownership. | `meta_catalog_routing.py` plus `turn_decision_v3`. | Ersetzt, aber alpha664 Decision-/Fallback-Verhalten ist known broken. |
| `aria/core/action_planner_scoring.py` | Keyword-, Template- und Bonus-Scores waehlen eine Aktion. | Begrenzte LLM-Auswahl aus registrierten Action-Kandidaten. | Deterministischer Gewinner bewusst entfernt. Tie-Break-Paritaet: **ABSICHT UNBEKANNT**. |
| `aria/core/action_planner_followups.py` | Statische Follow-up-Texte und Zielphrasen. | Sichtbarer Verlauf, `last_turn_frame` und Meta-Catalog-Decision. | Kein direkter Ersatz fuer alle alten UI-Vorschlaege; deren Erhaltungsabsicht ist **ABSICHT UNBEKANNT**. |
| `aria/core/chat_freshness.py` | Phrasenbasierte Web-/Aktualitaetsentscheidung plus separate LLM-Arbitration. | Meta-Catalog-Context-Decision und nachgelagerter Web-Source-Acquisition-Contract. | Semantik zentralisiert; Websuche ist aktuell known broken. |
| `aria/core/context_evidence.py` | Lexikalische Evidenz- und Inventarfilter fuer Kontextrelevanz. | Strukturierte Context-Requests, Source-bound Evidence, Loader-Contracts und bounded LLM-Relevanz/Review. | Freie Wortfilter bewusst entfernt; technische Evidenzvalidierung bleibt. |
| `aria/core/followup_resolution.py` | Separater LLM-/Regex-Pfad zum Umschreiben und Aufloesen von Follow-ups. | Eine Meta-Catalog-Decision mit sichtbarem Verlauf und letztem Turn-Frame. | Separate Vorautoritaet bewusst entfernt; robuste Follow-up-Paritaet noch nicht belegt. |

## Geloeschte Wortlisten

| Geloeschte Datei unter `aria/config/lexicons/` | Fruehere Rolle | Neuer Owner oder bewusste Entfernung | Status / Luecke |
| --- | --- | --- | --- |
| `action_planner_extractors.json` | Phrasen und Regex-nahe Extraktion von Action-Feldern. | Auf eine festgelegte Action begrenzte LLM-Input-Extraktion plus Action-Schema. | Bewusst keine freie Phrase-Extraktionsautoritaet mehr. |
| `action_planner_scoring.json` | Gewichte, Keywords und Boni fuer Action-Ranking. | LLM-Auswahl aus erlaubten Kandidaten; Contracts validieren nur. | Bewusst entfernt, kein Score-Ersatz. |
| `action_planner_templates.json` | Aktionstemplates und sprachliche Varianten. | Deklarierte Action-Metadaten, vorhandene Python-Templates, Connection-Contracts und Meta-Catalog. | Paritaet jedes alten Template-Felds: **ABSICHT UNBEKANNT**. |
| `auto_memory.json` | Trigger, Fallbacks und Muster fuer Auto-Memory. | `turn_semantics.py`, `learning_directive.py`, `personal_memory.py`, `learning_governor.py` und bounded Extractor/Synthesis. | Deterministisches Persistieren bewusst entfernt; E2E-Learning-Wirkung nicht belegt. |
| `capability_router.json` | Capability-, Intent-, Target- und Feldbegriffe. | `AriaTurnMenu`, `SurfaceRegistry`, Meta-Catalog und Action-Schemas. | Bewusst entfernt, kein Wortlisten-Ersatz. |
| `chat_admin_actions.json` | Begriffe und Tokenmuster fuer Admin-Aktionen. | Registrierte Admin-Actions, Menue-/Rollenbindung, Input-Contracts und Bestaetigungsledger. | Alte Shortcut-Paritaet: **ABSICHT UNBEKANNT**. |
| `chat_notes.json` | Natuerliche Note-Kommandos und Matching-Muster. | Notes-Surface und deklarierte Notes-Actions im Meta-Catalog. | Regex-Kommandoautoritaet entfernt; freie Sprachparitaet muss live belegt werden. |
| `chat_websites.json` | Begriffe fuer Website-Oeffnen und Website-Ziele. | Connection-/Website-Catalog und deklarierte Actions. | Alte Shortcut-Paritaet: **ABSICHT UNBEKANNT**. |
| `connection_catalog.json` | Sprachliche Connection-Typen, Aliase und Metadaten. | Strukturierter `connection_catalog.py`, konfigurierte Connection-Metadaten und Meta-Catalog. | Technische Typdaten bleiben; freie Sprachlisten entfernt. |
| `connection_semantic_resolver.json` | Begriffsbasiertes Connection- und Ziel-Matching. | Meta-Catalog-Kandidaten, exakte konfigurierte Treffer und schema-gebundene Input-Extraktion. | Disambiguierung fuer unbekannte Targets aktuell unzureichend. |
| `memory_assist.json` | Muster fuer Memory-, Server- und Scope-Aufloesung. | Turn-Decision-Context-Requests, Target-Scope, Personal Claims und Recall-Contract. | Plural-/Scope-Paritaet ist nicht vollstaendig belegt. |
| `pipeline_input_patterns.json` | Regex-Muster zum Strippen und Extrahieren von Commands, Messages und Queries. | Action-spezifische LLM-Input-Extraktion mit festem Schema. | Bewusst entfernt als freie Bedeutungsautoritaet. |
| `recipe_runtime.json` | Aktionsphrasen, Stopwoerter und Recipe-Matching. | Registrierte Recipe-Kandidaten, Recipe-Contracts und bounded LLM-Entscheidung. | Laufzeit bleibt; phrase-basiertes Ranking entfernt. |
| `routing.json` | Zentrale Capability- und Intent-Wortlisten. | Rollen-/Config-Menue, Connection Catalog, SurfaceRegistry und Qdrant Meta-Catalog. | Bewusst entfernt; dies ist der Kern des Refactors. |
| `routing_resolver.json` | Begriffs- und Score-basierte Aufloesung von Route und Ziel. | Meta-Catalog/Qdrant-Kandidaten, Config-gebundene Treffer und strukturierte Contracts. | Kein deterministischer Semantik-Ersatz; Clarify-Pfad aktuell zu schwach. |

## Neue Kernmodule und ihre Verantwortung

| Neues Modul | Vorgesehene Verantwortung | Darf nicht zur neuen Sonderfall-Autoritaet werden |
| --- | --- | --- |
| `turn_decision_contract.py` | Struktur und Kohaerenz einer Turn-Decision validieren. | Keine freie Bedeutung erraten. |
| `turn_semantics.py` | Einheitliche semantische Lane und Learning-/Memory-Autorisierung normalisieren. | Keine beliebige Action planen. |
| `meta_catalog_routing.py` | Begrenzte LLM-Entscheidung aus erlaubtem Weltbild erzeugen, einmal reparieren und materialisieren. | Keine nicht registrierten Faehigkeiten erfinden. |
| `answer_influence.py` | Nutzung von Claims/Hinweisen in finalen Antworten als Receipt erfassen. | Kein Routing entscheiden. |
| `learning_directive.py` | Typisierte Learning-Lanes und Capture-Entscheidung transportieren. | Keine Rohdaten ungeprueft aktiv machen. |
| `learning_governor.py` | Dedup, Quoten, Retention und Review-Wuerdigkeit kontrollieren. | Keine semantische Produktentscheidung aus Wortlisten treffen. |
| `learning_synthesis.py` | Rohartefakte zu kanonischen, reviewbaren Kandidaten verdichten. | Keine Aktivierung ohne Lifecycle/Review-Grenzen. |
| `personal_memory.py` | Strukturierte persoenliche Claims, Historie, Lifecycle und Qdrant-Persistenz. | Kein allgemeiner Dokument- oder Audit-Muellplatz werden. |
| `action_confirmation_ledger.py` | Signierte Bestaetigungen atomar und genau einmal konsumieren. | Keine Action semantisch auswaehlen. |
| `memory_recall_contract.py` | Technische Recall-Parameter vereinheitlichen. | Keine Relevanz durch feste Produktwortlisten entscheiden. |

## Entfernte Tests

Mit den Legacy-Komponenten wurden auch Tests entfernt, die deren Verhalten
festschrieben, darunter Tests fuer Capability Router, Admin-Actions,
Chat-Freshness, Follow-up-Resolution, Keyword-Router, Routing-Lexikon und
Turn-Intent-Arbitration.

Das Entfernen dieser Tests ist nur dann korrekt, wenn neue Contract- und
End-to-End-Tests dieselben produktrelevanten Nutzerfaelle abdecken, ohne die alte
semantische Autoritaet wieder einzufuehren. Diese vollstaendige Paritaet ist im
alpha664-Status nicht belegt.

## Kritische Lueckenpruefung

- Keine geloeschte Wortliste soll unter anderem Namen als neue freie
  Triggerliste wiederkehren.
- Rollen-, Rechte-, Safety- und Schema-Daten muessen weiterhin strukturiert
  vorhanden sein.
- Alte Komfortfaelle duerfen nur ueber allgemeine semantische Faehigkeit oder
  deklarierte Metadaten zurueckkehren, nicht durch neue Produkt-/Host-Sonderregeln.
- Wo ein alter Nutzerfall nicht abgedeckt ist, muss er als fehlender Use Case
  dokumentiert und getestet werden.
- Ob alle alten Komfortfunktionen absichtlich aufgegeben wurden, ist
  **ABSICHT UNBEKANNT**.

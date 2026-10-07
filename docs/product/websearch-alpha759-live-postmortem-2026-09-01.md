# WebSearch alpha759 Live Postmortem

Stand: 2026-09-01
Status: ERSTER KORREKTURRAIL ALS ALPHA760 GEBAUT / LIVE-REAKZEPTANZ AUSSTEHEND

## Evidence

- Live-Export: redigierter lokaler Alpha759-Chat-Export
- Getesteter interner Build: `0.1.0-alpha759`
- Vier Prompts benoetigten zusammen `88.6s`; nur ein Prompt lieferte direkt eine Webantwort.
- Die sichtbaren drei LLM-Abrechnungen summieren sich auf mindestens `32833` Tokens und `$0.127306`; der fehlgeschlagene iPhone-Turn weist keine Token-/Kostenwerte aus.

## Befunde

### W1 - Fast Answer verstaerkt Queries und Latenz

`welches ist die neuste apple watch ultra` benoetigte `31.6s`. Der gueltige Fast-Answer-Plan enthielt drei Queries und zwei bevorzugte Domains; der Skill materialisierte daraus sechs SearXNG-Queries. Der Source-Plan kostete `6824ms`, der Skill `3136ms`, die finale Antwort `6653ms`; bereits vor der Pipeline lagen `14908ms`.

### W2 - Unangeforderte Kalenderbindung blockiert Recall

`was ist das neueste iPhone` wurde in sechs Queries mit `2026` oder `August 2026` umgeschrieben, obwohl der User kein Jahr oder Monatsfenster genannt hatte. Danach fehlte eine bevorzugte Apple-Quelle und der vorhandene Authority-Gate stoppte nach `18.7s` mit `prefer_primary_current_fact_primary_missing`. Das verletzt den bestehenden Routing-Acceptance-Vertrag gegen blinden Jahreszahl-Zwang.

### W3 - Domain-Autoritaet ist breiter als Seitenrelevanz

Beim Apple-Watch-Turn wurden 19 Apple-Domain-Treffer als bevorzugt promotet und 0 gefiltert. Das Viererbudget enthielt eine passende Produktseite, aber auch allgemeine Sicherheitsupdates, Apple Community und Zubehoer. Domain-/Pfadautoritaet bleibt notwendig, darf aber nicht als Beleg verstanden werden, dass jede Seite die konkrete Produktfrage beantwortet.

### L1 - Vorgelagerte Entscheidung dominiert einfache Turns

`welche Version ist aktuell bei Home Assistant` benoetigte `19.2s`, obwohl die Pipeline nur `2ms` lief; `19195ms` lagen davor. Diese systemische Pre-Pipeline-Latenz ist belegt, aber nicht Teil des ersten WebSearch-Owner-Rails.

### R1 - Interne Release-Frage wurde falsch als SSH-Aktion geplant

`welcher interne ARIA Build ist aktuell` erzeugte nach `19.1s` einen bestaetigungspflichtigen SSH-Plan auf `ssh/ubnsrv-aiagent`. Der bestehende Confirmation-/Policy-Pfad verhinderte die Ausfuehrung, aber Route und Source Authority sind falsch. Dieser Routing-Befund bleibt ein eigener Folge-Rail und wird nicht durch WebSearch-Code kaschiert.

## Root Cause

1. `_web_source_sanitize_plan_for_request()` ist ein leerer Durchreicher und validiert unangeforderte Kalenderliterale nicht gegen den User-Prompt.
2. `_search_queries()` multipliziert bei Fast Answer bis zu zwei Planqueries mit bis zu drei Site-Targets und erlaubt danach sechs Requests.
3. Der Source-Quality-Gate klassifiziert URL-Target-Autoritaet, nicht semantische Seitenrelevanz; die Fast Lane ueberspringt eine separate Kuration.
4. Der grosse vorgelagerte Turn-Decision-Payload und die falsche Release->SSH-Entscheidung liegen ausserhalb des WebSearch-Skills und brauchen getrennte Akzeptanz.

## Korrekturgrenze

Der erste Rail aendert ausschliesslich kanonische WebSearch-Plan-/Skill-Owner:

- unangeforderte vierstellige Kalenderjahre aus geplanten Queries entfernen,
- explizit vom User genannte Jahre unveraendert erhalten,
- Fast-Answer-SearXNG-Requests hart und beobachtbar auf maximal drei begrenzen,
- Required-Site-Abdeckung vor Preferred-Sites und breiter Query priorisieren,
- Source-Authority, fail-closed, Profilwahl, Page-Fetch, Confirmation und Routing nicht aufweichen,
- keine zusaetzliche LLM-, Retry-, Fetch- oder Netzwerkstufe einfuehren.

Home-Assistant-Ambiguitaet, Release-Metadata-Routing, SSH, RSS, Connection-Auswahl und die allgemeine Pre-Pipeline-Latenz bleiben eingefrorene Folgeprobleme.

## Lokaler Korrekturstand

- Build-Nachtrag: Nach separater `FREIGABE: BUILD` wurde alpha760 intern gebaut/exportiert und isoliert netzlos geprueft. Evidence `.codex/aria_acceptance/websearch-alpha760-review-build.json`; noch keine fachliche Live-Reakzeptanz. Die nachfolgenden CODE-Gates dokumentieren den Stand vor diesem Build.
- Der WebSearch-Plan entfernt jetzt ausschliesslich vierstellige Jahre, die im Originalprompt nicht vorkommen; explizite Jahre und Domainziele bleiben erhalten.
- `fast_answer` ist auf maximal drei SearXNG-Requests begrenzt. Required-/Preferred-Site-Abdeckung kommt vor dem breiten Fallback; explizite `site:`-Queries bleiben unveraendert und werden nicht doppelt praefigiert.
- Das Current-Fact-Fail-Closed-Gate bewertet wieder den Originalprompt statt der materialisierten Provider-Query und behaelt damit das Aktualitaetssignal des Users.
- Fokus `69 passed`, Hochrisiko-Nachbarschaft `407 passed`, Vollsuite Exit `0` bei `2322` gesammelten Tests. Pyflakes `0`, Compileall, strict i18n, `322` Acceptance-JSONs und Diff-Hygiene sind gruen.
- Kein Build, Export oder Live-Test wurde ausgefuehrt. Die Live-Ziele fuer Qualitaet und Latenz sind erst nach separater Build-Freigabe und anschliessender User-Reakzeptanz belegbar.

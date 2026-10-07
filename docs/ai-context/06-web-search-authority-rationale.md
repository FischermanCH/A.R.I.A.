# Web Search Authority Rationale

Stand: 2026-08-09
Status: EVIDENCE/RATIONALE. Keine aktive Direktive. Fuer aktuelle Web-/Routing-Arbeit gelten `AGENTS.md`, `docs/AI_CONTEXT.md`, das aktive Slice-Dokument und `docs/ai-context/07-agentic-routing-acceptance-contract.md`.

## 1. Pfad-Autoritaet

Kurze Antwort: Der Pfad bleibt im `site:`-Ziel, weil `github.com/qdrant` und `github.com/MADPANDA3D/QDRANT-MCP` fachlich verschiedene Quellen sind, obwohl beide unter derselben Domain `github.com` liegen. Ein Kollaps auf `site:github.com` wuerde ein fremdes Repository als moegliche Primaerquelle fuer Qdrant zulassen.

Code-Referenzen:

- `aria/modules/web_search/skill.py:482`-`489`: `_source_plan_preferred_sites` extrahiert bevorzugte Ziele aus `preferred_domains` ueber `site_targets_from_text`, ohne sie auf die Domain zu reduzieren.
- `aria/modules/web_search/skill.py:548`-`564`: `_search_queries` baut daraus `site:{site} {query}`; bei `github.com/qdrant` entsteht also `site:github.com/qdrant ...`, nicht `site:github.com ...`.
- `aria/core/web_source_targets.py:34`-`50`: `normalize_site_target` normalisiert Domain plus Pfad und gibt `domain/path` zurueck, wenn ein Pfad vorhanden ist.
- `aria/core/web_source_targets.py:83`-`95`: `url_matches_site_target` prueft erst die Domain und danach den Pfad-Prefix. `https://github.com/qdrant/qdrant/releases` passt zu `github.com/qdrant`; `https://github.com/MADPANDA3D/QDRANT-MCP/...` passt nicht.
- `tests/test_searxng_client.py:813`-`889`: `test_web_search_skill_keeps_preferred_repository_path_authority` belegt den Fehlerfall konkret. Die erste Query muss `site:github.com/qdrant Qdrant latest stable release` sein; das offizielle Qdrant-Repo wird als `preferred_source` markiert, das fremde MCP-Repo nur als `weak_secondary`.

Bewusst so: Der Pfad ist Teil der Quellenautoritaet. Besonders bei Hostern wie GitHub, GitLab, Docker Hub oder Paketregistries ist die Domain allein zu grob.

## 2. Fail-closed fuer Geschwister-Repos

Kurze Antwort: Bei `required_primary` ist ein reines Fremd-Repo-Ergebnis keine "beste verfuegbare" Quelle, sondern keine gueltige Primaerquelle. Der angenommene Nutzerschaden ist: Eine falsche, aber plausibel aussehende Antwort aus einem Geschwister-/Integrationsrepo ist schlimmer als ein sichtbarer No-Source-Stopp.

Code-Referenzen:

- `aria/modules/web_search/skill.py:635`-`645`: Wenn `authority_mode == "required_primary"` ohne bevorzugte Ziele ankommt, stoppt der Gate direkt mit `required_primary_targets_missing`.
- `aria/modules/web_search/skill.py:648`-`667`: Ergebnisse werden in `preferred` und `others` getrennt; Treffer zaehlen nur, wenn `url_matches_site_target` auf eines der bevorzugten Ziele passt.
- `aria/modules/web_search/skill.py:667`-`677`: Wenn bei `required_primary` keine bevorzugten Treffer existieren, gibt `_apply_source_quality_gate` `[]`, Detail `required_primary_source_missing` und `quality_gate_failed=True` zurueck.
- `aria/modules/web_search/skill.py:907`-`944`: Der fehlgeschlagene Quality-Gate-Pfad wird als `SkillResult(success=False)` mit `error_code=web_source_no_reliable_sources` materialisiert.
- `tests/test_searxng_client.py:892`-`952`: `test_web_search_skill_required_primary_fails_closed_for_sibling_repository` belegt genau das reine Fremd-Repo `github.com/MADPANDA3D/QDRANT-MCP`; erwartetes Ergebnis ist `success is False` und `web_source_no_reliable_sources`.

Bewusst so: `required_primary` ist eine Wahrheits-/Autoritaetsgrenze, kein Ranking-Wunsch. Nebenwirkung: Wenn die Suchmaschine nur Geschwister-Repos liefert, bekommt der Nutzer erst einmal keine Antwort.

## 3. Snippet statt Fetch

Kurze Antwort: Die Pipeline entscheidet nicht durch einen eigenen "fetch preferred URL now"-Schritt. Sie reviewed die bereits im WebSearch-Ergebnis vorhandenen Source-Rows. Diese Rows enthalten entweder `page_excerpt_text`, wenn der WebSearch-Skill erfolgreich gefetcht hat, oder sonst nur das Snippet. Wenn die Rows nicht genuegen, kuratiert die Pipeline fail-closed oder versucht eine neue Suche; sie ruft die bevorzugte URL nicht selbst nachtraeglich ab.

Code-Referenzen:

- `aria/modules/web_search/skill.py:118`-`142`: Es gibt einen Page-Fetcher im Skill (`_default_page_fetcher`, `page_fetcher`).
- `aria/modules/web_search/skill.py:287`-`314`: `_result_fetch_candidates` waehlt explizite URLs und die ersten Suchresultate als Fetch-Kandidaten aus, begrenzt auf maximal drei.
- `aria/modules/web_search/skill.py:980`-`990`: Der Skill versucht fuer diese Kandidaten `_fetch_page_excerpts`.
- `aria/modules/web_search/skill.py:1007`-`1013`: Wenn ein Resultat nur ein Snippet hat, wird das Snippet ausgegeben; wenn Fetch versucht wurde, aber kein lesbarer Auszug kam, wird explizit gewarnt, daraus keine konkreten Seitendetails abzuleiten.
- `aria/modules/web_search/skill.py:1051`-`1059`: Die Metadata unterscheidet `search_results_with_page_excerpt` von `search_results_only`.
- `aria/core/pipeline.py:1950`-`1972`: `_web_source_review_rows` baut die Kurationszeilen aus `snippet` oder `page_excerpt_text`. Das ist die Stelle, an der die Pipeline mit vorhandener Evidenz arbeitet, statt eine URL neu abzurufen.
- `aria/core/pipeline.py:2440`-`2499`: `_curate_planned_web_search_context` gibt dem LLM nur diese `sources` plus Contract und verlangt eine Auswahl, nicht eine Antwort und keinen Fetch.
- `aria/core/pipeline.py:2584`-`2695`: Bei unzureichenden Quellen wird fail-closed oder mit einer neuen Suchquery wiederholt; kein nachgelagerter URL-Fetch wird gestartet.

Unklar: Eine historische Absicht "immer die bevorzugte Quelle automatisch fetchen" ist im aktuellen Code nicht belegt. Belegt ist nur der vorhandene bounded Fetch im WebSearch-Skill selbst, nicht ein Pipeline-Post-Curation-Fetch fuer bevorzugte Quellen.

## 4. Engine-Realitaet

Kurze Antwort: Die eingesetzten SearXNG-Engines koennen pfad-basiertes `site:domain/path` je nach Engine nicht verlaesslich honorieren. ARIA verlaesst sich deshalb nicht allein auf die Engine. Die intendierte Kompensation ist ein eigener Provider-/Quality-Gate nach der Suche: Ergebnisse, die nicht zum pfadbasierten Ziel passen, werden nachtraeglich entfernt; bei `required_primary` fuehrt das zu fail-closed.

Code-Referenzen:

- `aria/modules/web_search/skill.py:534`-`545`: `_filter_results_for_site_query` liest das `site:`-Ziel aus der Query und filtert die Provider-Ergebnisse selbst per `url_matches_site_target`; entfernte Treffer erscheinen als `removed={n} reason=site_query_target_miss`.
- `aria/modules/web_search/skill.py:780`-`790`: Diese Filterung wird fuer jede SearXNG-Antwort ausgefuehrt, bevor die Resultate gemerged und gerankt werden.
- `aria/modules/web_search/skill.py:603`-`633`: `must_have_domains` werden nochmals als Required-Sites validiert.
- `aria/modules/web_search/skill.py:648`-`677`: `preferred_domains` werden gegen die echten Result-URLs validiert; bei `required_primary` ohne Treffer wird geschlossen gestoppt.
- `aria/core/web_source_targets.py:83`-`95`: Die lokale Kompensation ist pfadbewusst.

Bekannte Einschraenkung: Die Live-Beobachtung `removed=10` plus `web_source_no_reliable_sources` trotz aktiver GitHub-Engine passt zu genau dieser Engine-Realitaet: Die Engine kann breit liefern, ARIA wirft die falschen Pfade danach weg. Das ist laestig, aber die Alternative waere, `github.com`-Geschwister als autoritativ durchzulassen.

Nebenwirkung: Der Suchpfad kann leer werden, obwohl die richtige Seite existiert. Das ist ein Recall-Problem, kein Grund, die Autoritaetsgrenze aufzuweichen.

## 5. Vorhandene Fetch-Faehigkeit

Kurze Antwort: Ja, es gibt Fetch-Faehigkeit, aber in zwei verschiedenen Bedeutungen. `website_read` liest konfigurierte Website-Connections als gespeicherte Quelle, nicht beliebige gefundene URLs. Der echte freie URL-/Page-Fetch fuer Websuche existiert im `WebSearchSkill`.

Code-Referenzen:

- `aria/core/pipeline.py:882`-`910`: Der Read-Operation-Resolver erlaubt `website_read` neben Feed/Mail/Calendar-Leseoperationen.
- `aria/core/pipeline.py:2941`-`2942`: `_execute_website_read` delegiert an den Capability-Executor.
- `aria/core/pipeline_capability_execution.py:178`-`190`: `execute_website_read` findet eine konfigurierte Website per `connection_ref` und gibt deren Text zurueck.
- `aria/core/website_runtime.py:66`-`94`: `build_website_read_text` rendert Titel, URL, Beschreibung, Tags und Config-Link; es fetch't den Remote-Inhalt nicht.
- `tests/test_pipeline.py:7783`-`7815`: `test_pipeline_executes_website_read_from_configured_source` belegt diesen konfigurierten Website-Read.
- `aria/modules/web_search/skill.py:118`-`131`: `_default_page_fetcher` kann HTTP(S)-HTML/Text laden.
- `aria/modules/web_search/skill.py:352`-`388`: `_fetch_page_excerpt` und `_fetch_page_excerpts` extrahieren bounded Page-Excerpts.
- `aria/modules/web_search/skill.py:849`-`905`: Wenn die User-Query eine explizite URL enthaelt und die Suche keine Ergebnisse liefert, wird direkt per `page_fetch` ein Source-Eintrag erzeugt.
- `tests/test_searxng_client.py:1494`-`1572`, `1574`-`1670`, `1672`-`1715`: Tests belegen Page-Fetch fuer offizielle Resultate, starke Domain-Matches ausserhalb der Top-2 und explizite URLs ohne Suchtreffer.
- `tests/test_pipeline.py:4688`-`4769`: Ein expliziter URL-Lesewunsch bleibt im WebSearch/Page-Excerpt-Pfad; `website_read` wird nicht als beliebiger URL-Fetch missbraucht.

Bewusst so: Eine gefundene `preferred_source` koennte mit dem vorhandenen `WebSearchSkill`-Fetcher gelesen werden, ohne Autoritaet oder Fail-close zu beruehren, wenn der Fetch erst nach erfolgreicher `url_matches_site_target`-Validierung passiert und ein fehlender/leer lesbarer Excerpt nicht zu einer fremden Quelle degradiert. `website_read` ist dafuer nicht der richtige Mechanismus, solange die URL nicht als konfigurierte Website-Connection existiert.

## Empfehlung des Designers

Fuer "#4: Version einer offiziellen Quelle zuverlaessig lesen" sollte ARIA die getestete Repo-Autoritaet unveraendert lassen: `github.com/qdrant` bleibt ein pfadbasiertes Source-Target, Geschwister-Repos bleiben fail-closed. Die robuste Loesung ist ein zweistufiger offizieller-Quellen-Pfad: zuerst Search/Discovery mit pfadbewusstem `site:` plus lokaler URL-Validierung, danach ein obligatorischer Page-Fetch genau der validierten Preferred-/Required-URL fuer konkrete Versions-/Release-Claims. Wenn der Fetch keinen lesbaren Inhalt liefert oder die Version nicht im `page_excerpt_text`/belegten Source-Metadatum vorkommt, soll die Antwort nicht raten, sondern klar sagen, dass die offizielle Quelle gefunden, aber nicht ausreichend auslesbar war, und optional die gefundene URL nennen.

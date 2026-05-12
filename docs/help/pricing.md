# ARIA Hilfe: Pricing und USD-Kosten

Stand: 2026-03-17

## Ziel

ARIA berechnet Kosten nur dann, wenn fuer das verwendete Modell ein Preis hinterlegt ist.
Es gibt keine Schaetzung fuer unbekannte Modelle.

Wichtig:

- alle normalen Chat-Aufrufe laufen in die Kosten- und Token-Erfassung
- auch Hilfs- und Admin-Aufrufe ueber LLM oder Embeddings werden zentral mitgezaehlt
- dazu gehoeren z. B. RSS-Metadaten, RSS-Gruppierung mit LLM, Runtime-Diagnostics, Rezept-Keyword-Generierung sowie RAG-/Memory-Embeddings

## Datenquelle

ARIA nutzt die LiteLLM-GitHub-Preisliste als primaere Preisquelle:

- `LiteLLM` wird über die öffentliche GitHub-Preisliste `model_prices_and_context_window.json` synchronisiert, ohne das LiteLLM-Python-Paket zu importieren
- ARIA speichert die letzte gute Kopie lokal unter `pricing.litellm_cache_file`
- die lokale Kopie wird beim Start oder manuell über `/stats` aktualisiert, wenn sie älter als `pricing.refresh_interval_days` ist
- falls GitHub nicht erreichbar ist, nutzt ARIA die letzte lokale Kopie weiter
- falls noch keine lokale Kopie existiert, nutzt ARIA einen kleinen ARIA-bundled Notfallseed
- lokale oder exotische Modelle können zusätzlich weiter in `config/config.yaml` unter `pricing` ergänzt werden
- ARIA liest keine Preise aus dem LiteLLM-Python-Paket; ein LiteLLM-Proxy kann trotzdem normal als Provider-Endpunkt genutzt werden

Wichtige Felder:

- `pricing.enabled`
- `pricing.currency`
- `pricing.last_updated`
- `pricing.source`
- `pricing.litellm_cache_file`
- `pricing.refresh_interval_days`
- `pricing.model_aliases.<geloggter-modellname>`
- `pricing.chat_models.<modell>`
- `pricing.embedding_models.<modell>`

Pro Modell können zusätzlich gepflegt werden:

- `source_name`
- `source_url`
- `verified_at`
- `notes`

## Berechnung

Chat:

- Input-Kosten: `prompt_tokens * input_per_million / 1_000_000`
- Output-Kosten: `completion_tokens * output_per_million / 1_000_000`

Embedding:

- Input-Kosten: `embedding_tokens * input_per_million / 1_000_000`

`total_cost_usd` ist die Summe der bekannten Teile.
Wenn kein Preis gefunden wird, bleibt der jeweilige Kostenanteil `null`.

## Verhalten bei unbekannten Modellen und Aliasen

- Modell ohne Preiseintrag: keine Kostenberechnung für dieses Modell
- Stats zeigen diese Modelle als "unbepreist" in der Coverage
- Es wird absichtlich nichts geraten
- ARIA versucht bei bekannten Anbieterfamilien grosszuegigere Aliase aufzufangen, z. B. `claude-sonnet` oder `anthropic/claude-3-5-sonnet-latest`
- Deployment-Aliase koennen ueber `pricing.model_aliases` auf einen kanonischen Preisnamen gemappt werden, z. B. `openai/embed-small: openai/text-embedding-3-small`

## Pflegeprozess

1. `/stats` öffnen und **Preise aktualisieren** ausführen.
2. ARIA lädt kurz die LiteLLM-GitHub-Preisliste und schreibt sie lokal in `pricing.litellm_cache_file`.
3. Beim normalen Start aktualisiert ARIA die lokale Kopie nur, wenn sie älter als `pricing.refresh_interval_days` ist.
4. Wenn GitHub nicht antwortet, nutzt ARIA die letzte lokale Kopie weiter und zeigt den Fehler im Pricing-Panel.
5. Eigene Deployments oder Vertrags-/Sonderpreise in `config/config.yaml` unter `pricing.chat_models` oder `pricing.embedding_models` ergänzen.
6. Eigene Preise mit `source_name: Manual` oder `notes: source=manual` markieren, wenn sie beim Refresh Vorrang vor Provider-Preisen behalten sollen.
7. Deployment-Aliase unter `pricing.model_aliases` auf den Preisnamen mappen.
8. Stats prüfen; unbekannte Modelle stehen in der Coverage als unbepreist.

Der Refresh ersetzt LiteLLM-Preise aus der Quelle, behält aber lokale Zusatzmodelle und markierte manuelle Overrides.

## Stats-Ansicht

`/stats` zeigt:

- Gesamt- und Durchschnittskosten
- Kosten pro Modell
- Requests und Kosten nach Quelle wie `chat`, `rss_metadata`, `rss_grouping` oder `rag_ingest`
- Pricing Coverage (gesehen vs bepreist)
- unbepreiste Modelle
- Preisquellen inkl. Verifikationsdatum

Die Token-/Kostenwerte decken nicht nur den sichtbaren Chat ab, sondern auch interne Modellaufrufe, sofern diese ueber die zentrale Metering-Schicht laufen.

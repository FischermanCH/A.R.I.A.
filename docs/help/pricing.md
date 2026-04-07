# ARIA Hilfe: Pricing und USD-Kosten

Stand: 2026-03-17

## Ziel

ARIA berechnet Kosten nur dann, wenn fuer das verwendete Modell ein Preis hinterlegt ist.
Es gibt keine Schaetzung fuer unbekannte Modelle.

Wichtig:

- alle normalen Chat-Aufrufe laufen in die Kosten- und Token-Erfassung
- auch Hilfs- und Admin-Aufrufe ueber LLM oder Embeddings werden zentral mitgezaehlt
- dazu gehoeren z. B. RSS-Metadaten, RSS-Gruppierung mit LLM, Runtime-Diagnostics, Skill-Keyword-Generierung sowie RAG-/Memory-Embeddings

## Datenquelle

ARIA arbeitet heute mit einer kleinen Mischform:

- `OpenAI` und `Anthropic` werden primär über den LiteLLM-Preiskatalog aufgelöst
- `OpenRouter` kann über die Models-API synchronisiert werden
- lokale oder exotische Modelle können zusätzlich weiter in `config/config.yaml` unter `pricing` ergänzt werden

Wichtige Felder:

- `pricing.enabled`
- `pricing.currency`
- `pricing.last_updated`
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

## Pflegeprozess

1. Offizielle Anbieter-Seite prüfen.
2. Preis in `config/config.yaml` aktualisieren.
3. `source_url` und `verified_at` mitpflegen.
4. ARIA neu laden (`./aria.sh restart`).
5. Stats prüfen.

## Stats-Ansicht

`/stats` zeigt:

- Gesamt- und Durchschnittskosten
- Kosten pro Modell
- Requests und Kosten nach Quelle wie `chat`, `rss_metadata`, `rss_grouping` oder `rag_ingest`
- Pricing Coverage (gesehen vs bepreist)
- unbepreiste Modelle
- Preisquellen inkl. Verifikationsdatum

Die Token-/Kostenwerte decken nicht nur den sichtbaren Chat ab, sondern auch interne Modellaufrufe, sofern diese ueber die zentrale Metering-Schicht laufen.

# ARIA Hilfe: Pricing und USD-Kosten

Stand: 2026-03-17

## Ziel

ARIA berechnet Kosten nur dann, wenn für das verwendete Modell ein Preis hinterlegt ist.
Es gibt keine Schaetzung für unbekannte Modelle.

## Datenquelle

Preise werden in `config/config.yaml` unter `pricing` gepflegt.

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

## Verhalten bei unbekannten Modellen

- Modell ohne Preiseintrag: keine Kostenberechnung für dieses Modell
- Stats zeigen diese Modelle als "unbepreist" in der Coverage
- Es wird absichtlich nichts geraten

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
- Pricing Coverage (gesehen vs bepreist)
- unbepreiste Modelle
- Preisquellen inkl. Verifikationsdatum

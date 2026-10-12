# ARIA Hilfe: Pricing und USD-Kosten

Stand: 2026-05-12

## Ziel

ARIA soll sichtbar machen, wie viel LLM- und Embedding-Nutzung kostet. Das gilt nicht nur für sichtbare Chat-Antworten, sondern auch für interne Agentic-Aufrufe wie Routing, Guardrail-Entscheide, RSS-Zusammenfassungen, Rezeptvorschläge und RAG/Memory-Embeddings.

ARIA berechnet Kosten nur, wenn für das verwendete Modell ein Preis bekannt ist. Unbekannte Modelle werden nicht geraten, sondern in `/stats` als unbepreist gezeigt.

Wichtig: Diese Werte sind lokale Nutzungsschätzungen und keine abrechnungsgenaue Provider-Rechnung. Token- und Kostenarchive folgen ihrer eigenen begrenzten Aufbewahrung; Native Traces verwenden standardmäßig sieben Tage. Beim Start und durch Wartung werden alte Runtime-Daten automatisch bereinigt. Persönliche Erinnerungen, Dokumente, Notizen und Rezepte sind keine Sweep-Ziele.

## Datenquelle

Primäre Quelle ist die LiteLLM-GitHub-Preisliste:

- ARIA synchronisiert `model_prices_and_context_window.json` aus dem LiteLLM-Repository
- ARIA importiert oder installiert dafür **nicht** das LiteLLM-Python-Paket
- die letzte gute Kopie wird lokal unter `pricing.litellm_cache_file` gecached
- beim Start oder manuell über `/stats` wird aktualisiert, wenn die Kopie älter als `pricing.refresh_interval_days` ist
- wenn GitHub nicht erreichbar ist, nutzt ARIA die letzte gute lokale Kopie
- wenn noch keine Kopie existiert, nutzt ARIA einen kleinen gebündelten Notfallseed

Ein LiteLLM-Proxy kann weiterhin normal als LLM-Provider genutzt werden. Das Pricing ist davon getrennt.

## Manuelle Overrides

Eigene Deployments, Provider-Aliase oder Vertrags-/Sonderpreise können in der Pricing-Admin-UI unter `/stats` gepflegt werden.

Wichtige Felder in `config/config.yaml`:

- `pricing.enabled`
- `pricing.currency`
- `pricing.litellm_cache_file`
- `pricing.refresh_interval_days`
- `pricing.model_aliases.<geloggter-modellname>`
- `pricing.chat_models.<modell>`
- `pricing.embedding_models.<modell>`

Manuelle Preise sollten mit `source_name: Manual` oder `notes: source=manual` markiert werden, wenn sie beim Refresh Vorrang behalten sollen.

Beispiel Alias:

```yaml
pricing:
  model_aliases:
    openai/embed-small: openai/text-embedding-3-small
    embed-small: openai/text-embedding-3-small
```

## Berechnung

Chat:

- Input-Kosten: `prompt_tokens * input_per_million / 1_000_000`
- Output-Kosten: `completion_tokens * output_per_million / 1_000_000`

Embeddings:

- Input-Kosten: `embedding_tokens * input_per_million / 1_000_000`

`total_cost_usd` ist die Summe der bekannten Teile. Wenn kein Preis gefunden wird, bleibt der Kostenanteil `null` und das Modell erscheint in der Coverage als unbepreist.

## Sichtbarkeit in `/stats`

`/stats` zeigt:

- Gesamt- und Durchschnittskosten
- geloggte USD und nachträglich geschätzte USD
- Token nach Modell
- Requests nach Quelle, z. B. `chat`, `routing`, `memory_recall`, `rss`, `runtime_diagnostics`
- Pricing Coverage für Chat- und Embedding-Modelle
- unbepreiste Modelle
- Preisquellen, Cache-Status und Refresh-Button
- manuelle Alias-/Preis-Overrides

Wenn ältere Token-Zeilen später durch neue Preise oder Aliase bepreist werden können, kann die geschätzte Summe höher sein als die ursprünglich geloggte Summe.

## Pflegeprozess

1. `/stats` öffnen.
2. **Preise aktualisieren** ausführen.
3. Coverage prüfen.
4. Für Provider-/Proxy-Namen Aliase setzen.
5. Für Sonderpreise manuelle Preise setzen.
6. Danach einen kleinen Prompt ausführen und prüfen, ob Chat-Details Tokens und USD zeigen.

## Fehlerbilder

- `0 tokens`, obwohl ein LLM sichtbar genutzt wurde: Metering-Bug im jeweiligen Action-Pfad.
- `n/a` oder unbepreist: Modellname ist nicht bekannt oder Alias fehlt.
- Refresh dauert sehr lange: GitHub/LiteLLM-Quelle prüfen; ARIA sollte auf Cache/Seed zurückfallen und nicht endlos warten.

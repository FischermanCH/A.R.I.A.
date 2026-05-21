# ARIA Hilfe: Pricing und USD-Kosten

Stand: 2026-05-12

## Ziel

ARIA soll sichtbar machen, wie viel LLM- und Embedding-Nutzung kostet. Das gilt nicht nur fuer sichtbare Chat-Antworten, sondern auch fuer interne Agentic-Aufrufe wie Routing, Guardrail-Entscheide, RSS-Zusammenfassungen, Rezeptvorschlaege und RAG/Memory-Embeddings.

ARIA berechnet Kosten nur, wenn fuer das verwendete Modell ein Preis bekannt ist. Unbekannte Modelle werden nicht geraten, sondern in `/stats` als unbepreist gezeigt.

Wichtig: Diese Werte sind lokale Usage-Schaetzungen und keine abrechnungsgenaue Provider-Rechnung. Fuer stabile Betriebs-Hygiene gilt standardmaessig eine **90-Tage-Retention** fuer Token-/Kosten-/Activity-Logs und den redigierten LLM-Debug-Log. Beim Start und in der Maintenance werden aeltere lokale Runtime-Logs automatisch bereinigt; Config-Backups sind Downloads und werden nicht dauerhaft in ARIA gesammelt.

## Datenquelle

Primaere Quelle ist die LiteLLM-GitHub-Preisliste:

- ARIA synchronisiert `model_prices_and_context_window.json` aus dem LiteLLM-Repository
- ARIA importiert oder installiert dafuer **nicht** das LiteLLM-Python-Paket
- die letzte gute Kopie wird lokal unter `pricing.litellm_cache_file` gecached
- beim Start oder manuell ueber `/stats` wird aktualisiert, wenn die Kopie aelter als `pricing.refresh_interval_days` ist
- wenn GitHub nicht erreichbar ist, nutzt ARIA die letzte gute lokale Kopie
- wenn noch keine Kopie existiert, nutzt ARIA einen kleinen gebuendelten Notfallseed

Ein LiteLLM-Proxy kann weiterhin normal als LLM-Provider genutzt werden. Das Pricing ist davon getrennt.

## Manuelle Overrides

Eigene Deployments, Provider-Aliase oder Vertrags-/Sonderpreise koennen in der Pricing-Admin-UI unter `/stats` gepflegt werden.

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
- geloggte USD und nachtraeglich geschaetzte USD
- Token nach Modell
- Requests nach Quelle, z. B. `chat`, `routing`, `memory_recall`, `rss`, `runtime_diagnostics`
- Pricing Coverage fuer Chat- und Embedding-Modelle
- unbepreiste Modelle
- Preisquellen, Cache-Status und Refresh-Button
- manuelle Alias-/Preis-Overrides

Wenn aeltere Token-Zeilen spaeter durch neue Preise oder Aliase bepreist werden koennen, kann die geschaetzte Summe hoeher sein als die urspruenglich geloggte Summe.

## Pflegeprozess

1. `/stats` oeffnen.
2. **Preise aktualisieren** ausfuehren.
3. Coverage pruefen.
4. Fuer Provider-/Proxy-Namen Aliase setzen.
5. Fuer Sonderpreise manuelle Preise setzen.
6. Danach einen kleinen Prompt ausfuehren und pruefen, ob Chat-Details Tokens und USD zeigen.

## Fehlerbilder

- `0 tokens`, obwohl ein LLM sichtbar genutzt wurde: Metering-Bug im jeweiligen Action-Pfad.
- `n/a` oder unbepreist: Modellname ist nicht bekannt oder Alias fehlt.
- Refresh dauert sehr lange: GitHub/LiteLLM-Quelle pruefen; ARIA sollte auf Cache/Seed zurueckfallen und nicht endlos warten.

# Pricing and USD Costs

Updated: 2026-05-12

## Goal

ARIA should show how much LLM and embedding usage costs. This includes visible chat answers and internal agentic calls such as routing, guardrail decisions, RSS summaries, recipe suggestions, and RAG/memory embeddings.

ARIA only calculates costs when it knows the price for a model. Unknown models are not guessed; they are shown as unpriced in `/stats`.

## Data source

The primary source is the LiteLLM GitHub pricing list:

- ARIA syncs `model_prices_and_context_window.json` from the LiteLLM repository
- ARIA does **not** import or install the LiteLLM Python package for this
- the last good copy is cached locally under `pricing.litellm_cache_file`
- startup or `/stats` refreshes the cache when it is older than `pricing.refresh_interval_days`
- if GitHub is unavailable, ARIA keeps using the last good local copy
- if no copy exists yet, ARIA uses a small bundled emergency seed

A LiteLLM proxy can still be used as a normal LLM provider. Pricing is separate from that.

## Manual overrides

Own deployments, provider aliases, or contract prices can be maintained in the pricing admin UI under `/stats`.

Important fields in `config/config.yaml`:

- `pricing.enabled`
- `pricing.currency`
- `pricing.litellm_cache_file`
- `pricing.refresh_interval_days`
- `pricing.model_aliases.<logged-model-name>`
- `pricing.chat_models.<model>`
- `pricing.embedding_models.<model>`

Manual prices should be marked with `source_name: Manual` or `notes: source=manual` when they should keep precedence during refresh.

Example alias:

```yaml
pricing:
  model_aliases:
    openai/embed-small: openai/text-embedding-3-small
    embed-small: openai/text-embedding-3-small
```

## Calculation

Chat:

- Input cost: `prompt_tokens * input_per_million / 1_000_000`
- Output cost: `completion_tokens * output_per_million / 1_000_000`

Embeddings:

- Input cost: `embedding_tokens * input_per_million / 1_000_000`

`total_cost_usd` is the sum of the known parts. If no price is found, that component stays `null` and the model appears as unpriced in coverage.

## Visibility in `/stats`

`/stats` shows:

- total and average costs
- logged USD and repriced/estimated USD
- tokens by model
- requests by source, such as `chat`, `routing`, `memory_recall`, `rss`, `runtime_diagnostics`
- pricing coverage for chat and embedding models
- unpriced models
- pricing sources, cache status, and refresh button
- manual alias/price overrides

If older token rows become priceable later through new prices or aliases, the estimated sum can be higher than the originally logged sum.

## Maintenance workflow

1. Open `/stats`.
2. Run **Refresh prices**.
3. Check coverage.
4. Add aliases for provider/proxy model names.
5. Add manual prices for special contracts.
6. Run a small prompt and check whether chat details show tokens and USD.

## Common problems

- `0 tokens` although an LLM was clearly used: metering bug in that action path.
- `n/a` or unpriced: model name is unknown or an alias is missing.
- Refresh takes very long: check GitHub/LiteLLM source reachability; ARIA should fall back to cache/seed and not wait forever.

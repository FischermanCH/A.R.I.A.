# ARIA Help: Pricing and USD Costs

Updated: 2026-04-06

## Goal

ARIA only calculates costs when it knows a price for the model in use.
It does not guess prices for unknown models.

Important:

- normal chat requests are included in token and cost tracking
- helper and admin-side LLM or embedding calls are also counted centrally
- this includes, for example, RSS metadata generation, RSS grouping with LLM, runtime diagnostics, recipe keyword generation, and RAG/memory embeddings

## Data sources

ARIA uses the LiteLLM GitHub pricing list as the primary pricing source:

- `LiteLLM` is synchronized from the public GitHub `model_prices_and_context_window.json` list without importing the LiteLLM Python package
- ARIA stores the last good copy locally under `pricing.litellm_cache_file`
- the local copy is refreshed on startup or manually through `/stats` when it is older than `pricing.refresh_interval_days`
- if GitHub is unavailable, ARIA keeps using the last local copy
- if no local copy exists yet, ARIA uses a small bundled emergency seed
- local or unusual models can still be added manually in `config/config.yaml` under `pricing`
- ARIA does not read prices from the LiteLLM Python package; a LiteLLM proxy can still be used as a normal provider endpoint

Important fields:

- `pricing.enabled`
- `pricing.currency`
- `pricing.last_updated`
- `pricing.source`
- `pricing.litellm_cache_file`
- `pricing.refresh_interval_days`
- `pricing.model_aliases.<logged-model-name>`
- `pricing.chat_models.<model>`
- `pricing.embedding_models.<model>`

Per model, ARIA can also store:

- `source_name`
- `source_url`
- `verified_at`
- `notes`

## Calculation

Chat:

- Input cost: `prompt_tokens * input_per_million / 1_000_000`
- Output cost: `completion_tokens * output_per_million / 1_000_000`

Embeddings:

- Input cost: `embedding_tokens * input_per_million / 1_000_000`

`total_cost_usd` is the sum of the known parts.
If no price is found, that cost component remains `null`.

## Unknown models and aliases

- Unknown model without a pricing entry: no cost calculation for that model
- Stats list these models as unpriced in coverage
- ARIA deliberately does not invent prices
- ARIA now tries to resolve common family aliases more generously, for example `claude-sonnet` or `anthropic/claude-3-5-sonnet-latest`
- Deployment aliases can be mapped through `pricing.model_aliases`, for example `openai/embed-small: openai/text-embedding-3-small`

## Maintenance workflow

1. open `/stats` and run **Refresh prices**
2. ARIA briefly loads the LiteLLM GitHub pricing list and writes it to `pricing.litellm_cache_file`
3. on normal startup, ARIA refreshes the local copy only when it is older than `pricing.refresh_interval_days`
4. if GitHub does not respond, ARIA keeps using the last local copy and shows the error in the pricing panel
5. add own deployments or contract prices in `config/config.yaml` under `pricing.chat_models` or `pricing.embedding_models`
6. mark own prices with `source_name: Manual` or `notes: source=manual` if they should keep precedence during refresh
7. map deployment aliases through `pricing.model_aliases`
8. check Stats; unknown models are listed as unpriced in the coverage section

Refresh replaces LiteLLM source prices, but keeps local additional models and marked manual overrides.

## Stats view

`/stats` shows:

- total and average cost
- cost by model
- requests and cost by source such as `chat`, `rss_metadata`, `rss_grouping`, or `rag_ingest`
- pricing coverage (seen vs priced)
- unpriced models
- price sources including verification date

This means the token and cost totals are not limited to visible chat answers. Internal model calls are also included as long as they use the central metering path.

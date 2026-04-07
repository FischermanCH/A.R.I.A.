# ARIA Help: Pricing and USD Costs

Updated: 2026-04-06

## Goal

ARIA only calculates costs when it knows a price for the model in use.
It does not guess prices for unknown models.

Important:

- normal chat requests are included in token and cost tracking
- helper and admin-side LLM or embedding calls are also counted centrally
- this includes, for example, RSS metadata generation, RSS grouping with LLM, runtime diagnostics, skill keyword generation, and RAG/memory embeddings

## Data sources

ARIA currently uses a mixed approach:

- `OpenAI` and `Anthropic` are primarily resolved through the LiteLLM pricing catalog
- `OpenRouter` can be synchronized through the Models API
- local or unusual models can still be added manually in `config/config.yaml` under `pricing`

Important fields:

- `pricing.enabled`
- `pricing.currency`
- `pricing.last_updated`
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

## Maintenance workflow

1. verify the official provider pricing
2. update the entry in `config/config.yaml` if needed
3. keep `source_url` and `verified_at` in sync
4. reload ARIA
5. check `/stats`

## Stats view

`/stats` shows:

- total and average cost
- cost by model
- requests and cost by source such as `chat`, `rss_metadata`, `rss_grouping`, or `rag_ingest`
- pricing coverage (seen vs priced)
- unpriced models
- price sources including verification date

This means the token and cost totals are not limited to visible chat answers. Internal model calls are also included as long as they use the central metering path.

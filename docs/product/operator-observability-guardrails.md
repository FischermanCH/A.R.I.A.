# Operator Observability Guardrails

Status: 2026-05-12

ARIA treats `/stats` as the operator cockpit before an internal or public build is trusted. The goal is not to show every metric; the goal is to make release blockers and cost-tracking blind spots impossible to miss.

## Guardrail Rows

The Operator Guardrail card is intentionally small and machine-addressable. Each row has a stable `key` in `aria/web/stats_routes.py`:

- `release`: release label/version metadata exists and matches update status.
- `gateway`: chat LLM, embeddings and memory embeddings stay behind the shared UsageMeter where applicable.
- `pricing`: all seen model usage can be priced or is explicitly shown as unpriced.
- `cost_tracking`: token logging, UsageMeter wiring and estimated-vs-logged cost gaps are checked.
- `recipe_memory`: optional Recipe Experience Memory reachability when metadata is available.
- `preflight`: startup checks from the current runtime.
- `health`: runtime health rollup.
- `updates`: public update status and update-path visibility.

## Status Semantics

- `ok`: release/update confidence is not blocked by this signal.
- `warn`: operator review is needed, but the install may still be usable.
- `error`: do not trust a public release/update path until the issue is fixed or explicitly accepted.

Cost and token tracking are deliberately strict: disabled token tracking or LLM/embedding calls outside the shared UsageMeter are release errors, not cosmetic warnings.

## Maintenance Rules

- Add a new row only if it changes release/update confidence.
- Give every row a stable `key`; tests should not depend on visual order alone.
- Keep manual pricing aliases and manual prices visible after refreshes.
- Do not hide optional/fresh-install states as failures; mark disabled optional systems as `ok` with a clear summary.
- Do not add live network probes to page render paths that already have cached/last-known status data.

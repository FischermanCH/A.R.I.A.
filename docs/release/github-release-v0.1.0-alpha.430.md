# ARIA 0.1.0-alpha430

This public alpha hotfix tightens deep source-bound search over uploaded document collections.

## Fixed

- Deep docs searches now request an exhaustive uploaded-document corpus scan before semantic top-k excerpts can answer. This prevents generic section wording such as "ingredients" or "composition" from being treated as enough evidence when the actual searched term is not present in the retrieved excerpts.
- Document search answers can now expose stronger corpus coverage for "is this term in any uploaded document?" style questions: scanned document count, scanned chunk count, per-term match counts, and source details for the scanned documents.

## Architecture Notes

- This is an evidence-policy fix, not a deterministic routing shortcut. The Meta-Catalog still chooses the docs/deep context contract; the Memory skill then performs the source-bound corpus scan required by that contract.
- Existing document inventory behavior from `0.1.0-alpha428` and negative-search corpus coverage from `0.1.0-alpha429` remain in place.

## Upgrade Notes

- Normal managed installs should use `/updates` or `./aria-stack.sh update`.
- Fixed-tag installs can use `fischermanch/aria:0.1.0-alpha.430`.
- Normal updates should recreate only the `aria` service and keep Qdrant, SearXNG, Valkey, and persistent volumes untouched.

## Docker Images

- `fischermanch/aria:0.1.0-alpha.430`
- `fischermanch/aria:alpha`


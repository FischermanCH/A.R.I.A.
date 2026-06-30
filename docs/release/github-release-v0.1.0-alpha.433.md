# ARIA 0.1.0-alpha433

This public alpha hotfix finishes the uploaded-document corpus scan answer path.

## Fixed

- Exhaustive document corpus scans now keep structured per-term evidence, including per-term hit counts and matched/unmatched terms.
- If the primary searched term has zero hits but supporting context terms have hits, ARIA now answers from the exhaustive scan coverage instead of treating the context-term hits as proof of a positive match.
- If the answer composer returns an empty or invalid response for this source-bound scan case, ARIA now falls back to a deterministic evidence summary from the completed corpus scan.

## Architecture Notes

- This does not add a deterministic router. The Meta-Catalog still selects the document surface and corpus scope; the deterministic part is only the presentation of already-loaded scan evidence.
- The fix is designed for questions such as "is this term present in any uploaded document?" where semantic top-k retrieval is not sufficient proof.

## Upgrade Notes

- Normal managed installs should use `/updates` or `./aria-stack.sh update`.
- Fixed-tag installs can use `fischermanch/aria:0.1.0-alpha.433`.
- Normal updates should recreate only the `aria` service and keep Qdrant, SearXNG, Valkey, and persistent volumes untouched.

## Docker Images

- `fischermanch/aria:0.1.0-alpha.433`
- `fischermanch/aria:alpha`

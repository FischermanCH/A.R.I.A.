# SearXNG in ARIA

Status: 2026-04-21

SearXNG is ARIA's preferred service for self-hosted web search.

ARIA uses SearXNG for:

- web search with sources
- controlled research through a dedicated stack service
- feeding results back into chat answers or context

## How ARIA uses SearXNG

Important:

- ARIA does not run a search engine "inside itself"
- ARIA talks to the SearXNG JSON API
- SearXNG stays a separate search service in the stack

That is intentional:

- web search stays replaceable
- the search service can be monitored independently
- ARIA does not need to host search logic on its own

## Why SearXNG is a good fit

For ARIA, SearXNG brings a few clear advantages:

- self-hosted and controllable
- JSON API works well with ARIA
- search profiles can be tuned per use case
- results can flow back into chat with sources attached

## Typical places inside ARIA

If you want to check or configure SearXNG inside ARIA, these places matter:

- `/connections`
- `/connections/types`
- `/config/connections/searxng`
- `/stats`

## What to check first when something breaks

If web search is not working:

- is the SearXNG service reachable in the stack?
- is the base URL correct?
- does the JSON API respond?
- was the profile saved cleanly?

For ARIA, SearXNG is not a small plugin. It is the dedicated search layer for web research.

# SearXNG in ARIA

Updated: 2026-05-12

SearXNG is ARIA's separate self-hosted search service for web search. ARIA uses the JSON API, not SearXNG code inside the app container.

## How ARIA uses SearXNG

- SearXNG runs as its own stack service
- default in-stack URL: `http://searxng:8080`
- ARIA profiles define search behavior and routing metadata
- chat answers can show web sources in details

## Typical use

- `search the web ...`
- `research on the web ...`
- specific profiles for YouTube, news, books, or general search

## Profile fields

- title and short description
- aliases and tags
- language
- SafeSearch
- categories
- preferred engines
- result count and time range

## Difference to RSS

RSS is better for curated recurring sources and news digests. SearXNG is better for open web search. Both can show sources in chat details.

## What to check first

- is the `searxng` service running in the stack?
- is the stack URL correct?
- does JSON search return results?
- does the profile have useful aliases/tags?
- are SafeSearch or categories too restrictive?

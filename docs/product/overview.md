# ARIA — Overview

## What ARIA is

ARIA is a small, modular AI assistant built for people who want control instead of platform sprawl.

It runs locally, keeps its architecture understandable, and combines:

- a browser-first chat interface
- structured memory with Qdrant
- configurable skills and automations
- modular connections to external systems
- explicit security and role boundaries

ARIA is intentionally **not** trying to become a giant “do everything” AI suite.  
It is designed to stay lean, inspectable, and extensible.

---

## Core idea

**Open the browser and start chatting.**

ARIA is built GUI-first:

- no API-first complexity for normal users
- no React / Node / build-chain burden
- no giant framework stack that hides the real logic

The goal is simple:

> One system, one config, one clear UI, real capabilities.

---

## What makes ARIA different

### 1. Small by design

ARIA is intentionally lightweight.

It does not aim to be:

- a heavy OpenWebUI clone
- a workflow maze
- a black-box “agent platform”

Instead, it aims to be:

- fast to understand
- cheap to run
- easy to adapt
- realistic to self-host

### 2. Modular instead of hard-wired

ARIA is moving toward a capability-based architecture.

That means the system thinks in actions such as:

- `file_read`
- `file_write`
- `feed_read`
- `webhook_send`
- `api_request`

and only then decides which connection or transport to use.

This keeps the system extensible and makes later user-defined extensions realistic.

### 3. Token-aware and practical

ARIA is built with token discipline in mind.

It avoids unnecessary orchestration overhead and tries to keep:

- prompts compact
- routing deterministic where possible
- memory useful instead of noisy

### 4. Local-first and self-host friendly

ARIA can run in a local network, on a small server, or in a containerized setup.

It is designed for people who want:

- local control
- predictable hosting
- clear deployment behaviour
- less dependency on third-party SaaS platforms

---

## What ARIA can do today

### Chat and memory

- browser-based chat UI
- typed memory system with:
  - facts
  - preferences
  - session context
  - rolled-up knowledge
- document collections for RAG uploads
- auto-memory extraction
- manual memory creation and editing
- memory search and maintenance views
- standalone Notes workspace under `/notes`
- Markdown-first notes with Qdrant-backed semantic search
- document upload directly in `Memory`
- `txt`, `md`, and `pdf` with embedded text supported for RAG v1
- grouped document management in `Memory Map`
- pre-alpha web search via self-hosted `SearXNG`
- watched websites as a lighter source type for pages without RSS feeds

### Skills and automation

- custom skill manifests as JSON
- step-based skill pipeline
- skill wizard in the UI
- import/export for custom skills
- runtime execution for structured skill steps

### Connections

ARIA already supports multiple connection types with dedicated config pages, health checks, stats visibility, and routing integration.

Current connection families include:

- `SSH`
- `Discord`
- `SFTP`
- `SMB`
- `Webhook`
- `HTTP API`
- `SearXNG`
- `Google Calendar`
- `Watched Websites`
- `RSS`
- `SMTP`
- `IMAP`
- `MQTT`

These are not only config entries. ARIA is gradually wiring them into natural-language capabilities in chat.

### Capability-based actions

Examples of what ARIA can already do:

- read and write remote files via `SFTP`
- access remote file areas via `SMB`
- read `RSS` feeds
- search the web via configured `SearXNG`
- ask for upcoming calendar events via configured `Google Calendar`
- send to `Discord`
- call configured `HTTP APIs`
- send to `Webhook` targets
- send and read mail via `SMTP` / `IMAP`
- publish to `MQTT`
- keep Markdown notes and use them as additional context for web research

### Security and operations

- login and roles
- admin mode vs user mode
- secure secret storage
- config UI with route-level access control
- stats and runtime health views
- delete / edit / test flows for connections

Current ALPHA boundary:

- ARIA is not yet a full multi-user system
- the current user mode is a reduced working view
- it is meant to separate everyday use from system configuration complexity
- later ownership, sharing, and RBAC for skills and resources are planned as a dedicated architecture block

---

## Why this matters

ARIA is not just a chat frontend.

It is becoming a compact local automation and assistant layer that can:

- remember relevant context
- keep explicit user-written notes separate from Memory
- talk to real systems
- stay understandable
- stay operable by one person or a small team

That makes it useful for:

- homelab environments
- internal team assistants
- self-hosted AI workflows
- local operational dashboards
- small automation hubs

---

## Design principles

ARIA is guided by a few strict principles:

### Browser-first

The browser is the main product surface.  
Normal users should not need CLI workflows for day-to-day use.

### Security before convenience

If something is potentially risky, ARIA should:

- restrict it by role
- confirm it explicitly
- keep the execution path understandable

### Modular growth

New capabilities should not require rewriting the whole system.

The architecture is being shaped so that:

- new connection types remain pluggable
- new capability families remain predictable
- future user-defined extensions can hook into the same system

### No unnecessary bloat

If a feature makes ARIA bigger, more fragile, and less understandable without strong value, it should not be added.

---

## Target direction

ARIA is moving toward a model where:

- capabilities are routed cleanly
- memory helps resolve context
- connections remain modular
- the UI stays clear even as functionality grows
- user-defined connection and capability extensions become feasible later through structured definitions

In short:

> ARIA should feel like a capable local assistant, not like a giant AI control panel.

---

## One-line summary

**ARIA is a lean, modular, self-hosted AI assistant with memory, skills, secure connections, and a browser-first interface built for real control instead of platform bloat.**

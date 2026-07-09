# Agentic Operator

Updated: 2026-07-09

## Target model

ARIA should feel less like a bot with tools and more like a controlled personal operator:

1. understand the goal
2. load context
3. plan the step
4. decide safety
5. execute
6. summarize the result
7. optionally learn from review and feedback

LLMs help with meaning, planning, summarization, and review. Safety, guardrails, runtime, validation, normalization, and fallbacks stay controlled system layers.

## Operator Trace

Chat Details can include `operator_trace` lines. They summarize existing debug/runtime signals into readable phases:

- **understanding**: what ARIA understood from the prompt
- **context**: which local or external sources were loaded
- **draft/policy**: which action was planned and which safety decision was made
- **runtime**: which runtime actually executed
- **result**: what the runtime returned
- **summary**: answer and runtime completion
- **learning**: review/context learning only, not automatic policy changes

The trace is observability, not permission. It does not replace guardrails and does not execute actions by itself.

## Actions and guardrails

Read-only actions such as health checks, disk-space checks, RSS reads, or API status checks can run directly when policy and guardrails allow them.

Side effects such as sending messages, calling webhooks, writing files, or risky commands may be blocked or require confirmation.

## Context sources

Depending on the prompt, ARIA can combine:

- Memory and preferences
- documents and document inventory
- Notes
- connections and their metadata
- recipes and learned experience
- web search when current public information is needed

Current product/version questions should prefer web freshness and official sources. Local documents remain relevant when the prompt explicitly asks about the local document store.

## Learning

Learned patterns are planner context and review material. They must not bypass guardrails. Multi-target or side-effect experience stays cautious and must be reviewed deliberately before becoming an executable recipe.

## Useful update tests

- ask a read-only server question and inspect Details for context, runtime, and result
- plan a confirmation-required action and do not execute it
- ask a current product question and check sources
- ask a local document inventory question and make sure it does not drift into web search

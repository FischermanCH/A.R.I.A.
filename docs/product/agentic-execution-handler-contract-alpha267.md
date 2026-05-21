# Agentic Execution Handler Contract - alpha267

Status: first extraction, SSH multi-target and RSS feed reads are the pilot adapters.

## Goal

ARIA's agentic runtime should not become a hard-coded list of provider branches in `pipeline.py`.
The target shape is a general execution contract where connection families can hook in their own
runtime behavior while still using ARIA's common boundaries:

- bounded planner payload
- deterministic policy and guardrail preflight
- runtime adapter execution
- operator summary
- context memory
- Learned Recipe recording and review-only follow-up

This is the foundation for future community-defined connections: protocol and auth can vary, but
the execution adapter must declare how it receives a bounded payload, how it validates/preflights,
how it executes, and what evidence it returns.

## Current Contract

`aria/core/agentic_execution.py` defines the shared runtime surface:

- `AgenticExecutionRequest`: resolved routing/action payload, action decision, user id, language
- `AgenticExecutionResult`: pipeline-compatible intents, answer text, detail lines, errors
- `AgenticExecutionHandler`: `can_handle(request)` plus async `execute(request)`
- `AgenticExecutionHooks`: common callbacks supplied by the orchestrator for formatting, debug,
  missing-input handling, execution errors, and capability detail lines
- `AgenticExecutionRegistry`: selects the first handler whose `can_handle()` claims the request
- `AgenticExecutionLearningService`: shared recording path for successful capability execution,
  Learned Recipe updates, and review-memory follow-up scheduling

Provider-specific handlers extend this with their own hooks. The current adapters are:

- `MultiTargetSSHExecutionHandler` in `aria/core/agentic_ssh_execution.py`
- `RSSFeedExecutionHandler` in `aria/core/agentic_rss_execution.py`

## Adapter Rule

New connection adapters should follow this pattern:

1. Check ownership in `can_handle()` using normalized `connection_kind`, `capability`, and payload shape.
2. Treat the bounded payload as input, not as permission to bypass policy.
3. Run deterministic preflight before runtime execution.
4. Return structured `AgenticExecutionResult`; do not write directly to chat state.
5. Record memory/learning through hooks so the orchestrator can keep policy and review gates central.
6. Keep provider-specific protocol/auth behavior inside the adapter or its runtime, not in `pipeline.py`.

## Adapter Template

New adapters should look like this at minimum:

```python
class ExampleExecutionHandler:
    def can_handle(self, request: AgenticExecutionRequest) -> bool:
        payload = request.payload
        return payload.get("connection_kind") == "example" and payload.get("capability") == "example_action"

    async def execute(self, request: AgenticExecutionRequest) -> AgenticExecutionResult:
        plan = hooks.payload_to_action_plan(request.payload)
        # 1. deterministic preflight / policy
        # 2. runtime execution through a bounded adapter
        # 3. hooks.remember_action(...)
        # 4. hooks.learning_service.record_capability_success(...)
        return AgenticExecutionResult(
            intents=[f"capability:{plan.capability}"],
            text=result_text,
            detail_lines=detail_lines,
            errors=[],
        )
```

Registration happens by adding the handler to the registry factory, not by adding another
execution branch to `_execute_routed_action()`.

## Current Pilots

SSH multi-target execution now uses the handler path for:

- per-target guardrail/policy preflight
- per-target runtime execution
- detail-line/debug collection
- capability context memory
- Learned Recipe recording with `plural_target_scope`
- deterministic and LLM-backed operator summary

RSS feed execution now uses the same handler registry for:

- RSS group-bundle enrichment
- digest option extraction
- runtime execution via the shared capability executor
- context memory
- Learned Recipe recording and follow-up

The next adapters should reuse this surface instead of adding new provider-specific execution
branches to `pipeline.py`.

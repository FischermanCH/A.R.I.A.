# Connection Provider Manifest Checklist

Status: 2026-05-12

This checklist is the bridge from today's Python-backed connection contracts to future declarative provider manifests. It keeps new connection types modular without forcing provider-specific logic back into `pipeline.py`.

## Required Manifest Fields

A future provider manifest needs to map cleanly to the current `ConnectionActionContract` export:

- `capability`: canonical action capability such as `ssh_command`, `feed_read`, or `discord_send`.
- `family`: operator-level action family such as `command`, `file`, `message`, `read`, or `request`.
- `operation`: runtime operation shown in `agentic_runtime`, for example `run_command`, `read`, `send`, `publish`, or `request`.
- `executors`: supported connection kinds.
- `policy_family`: policy/guardrail family that decides allow/ask/block.
- `required_fields`: `ActionPlan` fields required before runtime execution.
- `payload_fields`: bounded fields allowed in runtime debug payloads.
- `side_effect`: whether the action can change external state or send data.

## Required Runtime Boundaries

Every new connection provider must preserve these boundaries:

- Context enrichment may suggest a target or capability, but it may not authorize execution.
- The LLM may draft only bounded action payloads.
- Policy/guardrails decide allow, ask, or block.
- Runtime adapters execute only after the contract and policy boundaries are satisfied.
- Debug output must show enough payload to audit the action without exposing secrets.

## Tests To Add With A New Provider

- Capability executor binding is covered by `connection_action_contract()`.
- `connection_action_manifest_rows()` exports the capability with policy, runtime operation and side-effect state.
- Side-effect providers use a non-read-only policy family.
- Runtime debug payload comes from the contract, not from local `if capability == ...` chains.
- Any UI/config surface stays provider-specific while planner/pipeline logic stays generic.

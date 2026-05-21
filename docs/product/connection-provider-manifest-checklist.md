# Connection Provider Manifest Checklist

Status: 2026-05-16

This checklist is the bridge from today's Python-backed connection contracts to future declarative provider manifests. It keeps new connection types modular without forcing provider-specific logic back into `pipeline.py`.

The first internal contract lives in `aria/core/connection_provider_manifest.py`. It does not load
community providers yet; it exports and validates provider-shaped manifests from the current
`ConnectionActionContract` source of truth.

## Required Manifest Fields

A provider manifest needs to map cleanly to the current `ConnectionActionContract` export:

- `schema_version`: current internal schema, currently `0.2`.
- `provider_id`: stable provider id such as `builtin.ssh` or future `community.example`.
- `connection_kind`: canonical connection kind, such as `ssh`, `rss`, or `http_api`.
- `display_name`: human-readable provider label.
- `runtime_adapter`: runtime adapter id. Built-ins currently use `builtin.<connection_kind>`.
- `auth_modes`: supported authentication modes, such as `ssh_key`, `oauth2`, `api_key`, or `none`.
- `capabilities`: list of capability rows.

Each capability row contains:

- `capability`: canonical action capability such as `ssh_command`, `feed_read`, or `discord_send`.
- `family`: operator-level action family such as `command`, `file`, `message`, `read`, or `request`.
- `operation`: runtime operation shown in `agentic_runtime`, for example `run_command`, `read`, `send`, `publish`, or `request`.
- `planner_role`: planner-level role such as `read`, `search`, `send`, `write`, `command`, `request`, `publish`, or `list`.
- `policy_family`: policy/guardrail family that decides allow/ask/block.
- `guardrail_kind`: optional guardrail family key.
- `required_fields`: `ActionPlan` fields required before runtime execution.
- `payload_fields`: bounded fields allowed in runtime debug payloads.
- `side_effect`: whether the action can change external state or send data.
- `confirmation_required`: whether execution must pass an explicit confirmation step.
- `sensitive_content`: whether the action can expose private user/content data to summaries.
- `draft_capability`: optional draft-only capability that should precede a send/write side effect.
- `direct_capability_gate`: whether the provider can be routed through the direct capability gate.

## Required Runtime Boundaries

Every new connection provider must preserve these boundaries:

- Context enrichment may suggest a target or capability, but it may not authorize execution.
- The LLM may draft only bounded action payloads.
- Policy/guardrails decide allow, ask, or block.
- Runtime adapters execute only after the contract and policy boundaries are satisfied.
- Debug output must show enough payload to audit the action without exposing secrets.
- Read/search actions may expose sensitive content only through bounded summaries and source-aware detail lines.
- Send/write/publish actions must be confirmation-gated and should have a draft/review step when user-facing content is generated.

## Tests To Add With A New Provider

- Capability executor binding is covered by `connection_action_contract()`.
- `connection_action_manifest_rows()` exports the capability with policy, runtime operation and side-effect state.
- `connection_provider_manifest_rows()` exports a provider-level row for the connection kind.
- `validate_connection_provider_manifest()` passes for the provider row.
- Side-effect providers use a non-read-only policy family.
- Runtime debug payload comes from the contract, not from local `if capability == ...` chains.
- Read/search/send/write semantics come from `planner_role`, not provider-specific pipeline branches.
- Sensitive-content and confirmation metadata is declared in the contract and exported in the manifest.
- Any UI/config surface stays provider-specific while planner/pipeline logic stays generic.

## Email-Style Provider Target

E-mail is the reference provider family for the next modularity step:

- `mail_search`: find relevant messages by sender, subject, text, date or mailbox scope.
- `mail_read`: read bounded message content for summarization and question answering.
- `email_send`: send a new message only after confirmation; generated text should first be treated as an `email_draft`.
- Future `email_reply`: same send boundary, but with an explicit source message/thread reference.
- Future mailbox mutations such as archive, label or delete need separate capabilities and stricter policy rows.

The same shape should also fit future ticket, notes, files, calendar and chat providers: read/search first, draft next, side-effect execution last.

## Current Built-In Export

The internal provider-manifest export groups the current action contracts into provider rows for:

- `discord`
- `email`
- `google_calendar`
- `http_api`
- `imap`
- `mqtt`
- `rss`
- `sftp`
- `smb`
- `ssh`
- `webhook`
- `website`

This is intentionally contract-only. Importing or enabling third-party provider manifests remains a
future step after the runtime adapter and auth-secret boundaries are hardened.

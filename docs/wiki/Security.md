# Security, Secrets, and Guardrails

Updated: 2026-05-12

## Purpose

This page explains how ARIA stores sensitive values and how the current alpha security model works: login, secure store, CSRF, guardrails, and confirmation-required actions.

## What is stored encrypted

The secure DB (`data/auth/aria_secure.sqlite`) currently stores:

- LLM and embedding API keys
- profile API keys and tokens for connections
- user credentials with password hash and role
- additional runtime secrets when a module stores them there

Passwords are not stored in plaintext. Secrets are encrypted with AES-256-GCM.

## Where the key lives

The master key lives in `config/secrets.env`:

- `ARIA_MASTER_KEY`
- `ARIA_AUTH_SIGNING_SECRET`
- `ARIA_FORGET_SIGNING_SECRET`

Recommended permissions: `600`.

These values must not be committed to git. If they are missing, ARIA creates persistent values on first start.

## Cleartext to secure DB migration

```bash
./aria.sh secure-migrate
```

This copies secrets from `config/config.yaml` into the secure DB, clears YAML fields, and writes a backup.

## Login and sessions

- login URL: `/login`
- session cookie is signed
- user names are case-sensitive
- disabled or removed users lose their session immediately
- the first bootstrap user becomes admin while bootstrap is not locked
- admin mode and role are separate: only admins can use admin features at all

## CSRF and browser protection

State-changing browser requests are protected with CSRF tokens:

- cookie: `aria_csrf_token`
- forms include the token automatically
- fetch/HTMX sends `X-CSRF-Token`
- missing or invalid tokens are rejected with `403`

ARIA also sets default security headers such as CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, and `Permissions-Policy`.

## Guardrails for actions

The Agentic Action Flow separates:

1. **Draft**: What might the user mean?
2. **Policy/Guardrail**: Is it allowed, should it ask, or must it be blocked?
3. **Runtime**: What is actually executed?

Possible policy results:

- `allow` - execute
- `ask_user` - ask for chat confirmation
- `block` - do not execute

Examples:

- read-only SSH such as `df -h` or health checks: can be allowed
- service restarts: blocked by default or require explicit admin policy
- Discord/Webhook sends: ask for confirmation

## One-click confirmation

When ARIA should not execute an action directly, chat shows a button such as **Run action**. This replaces fragile manual token copying for normal use. The older confirmation-code path can remain as a fallback, but should not be the preferred UX.

## Public alpha boundary

ARIA is intended for controlled environments:

- LAN/VPN or reverse proxy with proper auth
- no secrets in the image
- no secrets in git
- volumes for persistent data
- updates through managed helper or deliberate host commands

Direct public internet exposure without additional protection is not recommended for the alpha.

## Troubleshooting

- `ARIA_MASTER_KEY missing`: check `config/secrets.env` and start through the intended path.
- new keys do not take effect: check `security.enabled`, secure DB path, and restart.
- action is blocked: read chat details; policy and guardrail reason are shown there.
- confirmation button does not execute: check browser/CSRF/session and the chat detail type `routed_action_pending`.

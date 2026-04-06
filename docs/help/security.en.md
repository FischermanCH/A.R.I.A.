# ARIA Help: Security and Secrets

Updated: 2026-04-06

## Purpose

This document explains how ARIA stores sensitive values, how secret handling works, and how the current alpha security model is structured.

## What is stored encrypted

In the secure DB (`data/auth/aria_secure.sqlite`), ARIA currently stores:

- `llm.api_key`
- `embeddings.api_key`
- `channels.api.auth_token`
- profile API keys such as:
  - `profiles.llm.<name>.api_key`
  - `profiles.embeddings.<name>.api_key`
- user credentials (user, password hash, role)

Notes:

- passwords are not stored in plaintext; they use Argon2 hashes
- secrets are stored encrypted with AES-256-GCM

## Where the key lives

The master key is stored in:

`config/secrets.env`

Important variables:

- `ARIA_MASTER_KEY`
- `ARIA_AUTH_SIGNING_SECRET`
- `ARIA_FORGET_SIGNING_SECRET`

Notes:

- these secrets must not be committed to git
- if they are not provided, ARIA generates persistent runtime values on first start in `config/secrets.env`
- secret resolution is centralized in `aria/core/config.py`

Recommended file permissions:

- `600`

## Cleartext to secure DB migration

Command:

`./aria.sh secure-migrate`

What happens:

1. a master key is created if missing
2. secrets from `config/config.yaml` are copied into the secure DB
3. API key fields are cleared from the YAML file
4. a backup is written

## Git and container readiness

For a clean public-repo and container workflow, these stay local:

- `config/config.yaml`
- `config/secrets.env`
- `data/auth/`
- `data/logs/`
- `data/skills/`

The repo should only contain examples such as:

- `config/config.example.yaml`
- `config/secrets.env.example`

## Login and sessions

- login URL: `/login`
- session cookie is signed
- user names are case-sensitive
- if a user is disabled or removed, the session becomes invalid immediately
- current login timeout is configurable in the UI

## CSRF protection

ARIA protects state-changing browser requests with a CSRF token:

- cookie: `aria_csrf_token`
- forms include the token automatically
- fetch/HTMX requests send `X-CSRF-Token`
- the server validates token and cookie together

Invalid or missing tokens are rejected with `403`.

## Security headers

ARIA sets default browser security headers, including:

- `Content-Security-Policy`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy`
- `Permissions-Policy`

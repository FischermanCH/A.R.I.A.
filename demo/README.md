# ARIA demo instance

This stack is a durable, isolated screenshot and product-tour environment. It
uses only the `aria-demo` Compose project, the `aria-demo-data` and
`aria-demo-qdrant` volumes, the `aria-demo-net` network, and port `8090` by
default. It never mounts ARIA production configuration or data.

- URL: `http://localhost:8090`
- Login: `demo-admin`
- Password: `aria-demo-access`

Use the current local image by setting `ARIA_DEMO_IMAGE` (the demo scripts
default to `fischermanch/aria:0.1.0-alpha.1007`):

```bash
scripts/demo/start.sh
scripts/demo/stop.sh
scripts/demo/reset.sh
```

`reset.sh` removes only resources whose exact Compose project/name starts with
`aria-demo`, recreates the deterministic fictitious seed, and starts it again.
Set `ARIA_DEMO_PORT` to change the host port. Pages and prepared chats work
without a language-model provider: the `llm-stub` service
(`scripts/demo/llm_stub.py`) answers LLM buttons such as guardrail drafts and
connection metadata with fixed fictitious JSON and never contacts a provider.
The demo ARIA container has no outbound internet (proxy block), so the prepared
«update available» state and the connection status cache from
`scripts/demo/seed_features.py` stay deterministic. For optional live chat, set
the normal LLM fields in `demo/generated/config/config.yaml` to an endpoint
dedicated to this demo; never point it at a production data volume.

The seed contains no real people, hosts, addresses, paths, credentials, tool
outputs or documents. The published login above is a deliberate demo
credential, not a secret.

Validate every rendered page, theme roles and public safety with:

```bash
python3 scripts/demo/check_ui.py --url http://127.0.0.1:8090
python3 scripts/demo/check_public_safety.py --url http://127.0.0.1:8090
```

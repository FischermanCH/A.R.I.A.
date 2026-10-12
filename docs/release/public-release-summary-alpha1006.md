# ARIA Alpha1006 public release summary

Alpha1006 is the reviewed candidate for the next public ARIA alpha after Alpha983. It combines the internal work from Alpha984 through Alpha1006. Publishing the image, source tag and GitHub release remains a separate owner-controlled step.

## Highlights since Alpha983

- **Activity Journal and legacy rollups:** completed Tool turns and terminal Agent Jobs can create compact, redacted, user-scoped journal entries. Legacy context rollups remain untouched until a user previews and explicitly imports or deletes already imported rows.
- **Owner-focused statistics with Alpha983 parity:** `/stats` restores every owner check and model role from the public Alpha983 surface unless it is explicitly documented as intentionally removed. Concrete linked problems and group counts are immediately visible; detailed green/yellow/red check tiles load only when their collapsed group is opened. The initial GET remains passive and prices remain limited to relevant models.
- **Reliable background work:** Agent Jobs gained durable completion delivery through an outbox, cross-worker chat-history locking, exact-once pause/budget notices, controls, correction, confirmation and safe Markdown results.
- **Chat presentation:** ordinary answers and Job notices share the same escaped Markdown renderer. Bounded tables cannot widen the page, the composer stays reachable, and an empty progress element no longer leaves a blank bar.
- **iPhone/Safari usability:** portrait and landscape use normal page scrolling, a non-wrapping one-row header and a safe-area-aware sticky composer. An admin-only diagnostic exposes on-device geometry without sending it anywhere.
- **Local time and Journal periods:** one configurable display time zone is shared by chat, Jobs, statistics, the Activity Journal and its read Tool. The Journal uses an explicit All/Today/7 days/30 days/Custom selector.
- **UI clarity and consistency:** shared page-type templates, canonical navigation, explicit action/settings/danger patterns and rules R1–R32 cover the bilingual administration. Eleven themes share central component roles and computed-style checks.
- **MCP resilience and latency:** discovery, reconnection and failed-server backoff stay outside the synchronous turn path; Tool selection, confirmation and honest failures remain unchanged. Recipe manifests use a non-blocking warmed snapshot.
- **Deterministic demo:** an isolated `aria-demo` stack on port 8090 contains only reproducible fictitious data and works without a language model. It is the sole source of the public screenshots.
- **Data hygiene:** operational traces and ephemeral runtime stores have bounded retention. Configuration backups exclude secrets and password hashes by default; credentials are optional only as a passphrase-encrypted bundle. Memories, documents, notes and recipes are not swept automatically.

## Boundaries

- ARIA remains an alpha aimed primarily at personal LAN/VPN or homelab use.
- It is not a finished multi-user permission platform and should not be exposed directly to the public internet.
- MCP and connection behavior depends on the external systems the operator explicitly configures.
- Screenshot and demo data is synthetic and does not demonstrate a real provider or productive connection.

## Upgrade notes

Create a configuration backup and preserve the ARIA data/config mounts and Qdrant volume. Normal managed updates recreate only the ARIA service. Alpha1006 does not require users to delete memories, documents, recipes or legacy rollups. Old `auto_memory` and context-compression settings continue to load tolerantly where documented, but their retired writers and controls are not restored.

The isolated gates cover fresh installation plus upgrades from the older public Alpha604 line and from Alpha983. Publication must use the already accepted immutable image without rebuilding it.

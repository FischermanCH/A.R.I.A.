# ARIA Alpha1007 release candidate

Alpha1007 keeps the Alpha1006 public-candidate scope and polishes the two most visible owner surfaces before publication.

## What changed since Alpha983

- Native Agent Jobs can detach, notify, pause, resume, be corrected and be inspected without losing chat delivery.
- MCP clients discover and reuse sessions resiliently, use the confirmation kernel for untrusted mutating tools, and support bounded vision results.
- The Activity Journal records compact, user-scoped summaries without raw tool output and offers explicit migration of legacy rollups.
- Administration uses shared page types and theme roles across German and English surfaces.
- Owner statistics cover health, cost, activity and resources without provider calls on page load.
- Alpha1007 removes duplicate statistics checks, fixes routing-index drift, corrects storage measurements and simplifies chat actions.

## Honest limits

ARIA remains primarily designed for a trusted single-user or household deployment. External MCP servers are separate trust boundaries. Local cost figures are estimates, not provider invoices. The Activity Journal never replaces personal memories, documents, notes or recipes.

## Upgrade

Back up configuration and data, retain the existing data/config mounts and Qdrant volume, then replace only the ARIA image. Alpha1007 does not silently delete memories, documents, notes, recipes or legacy rollups.

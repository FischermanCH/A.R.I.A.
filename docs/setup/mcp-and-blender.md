# MCP and Blender setup

ARIA can use tools exposed by an enabled Model Context Protocol (MCP) server over HTTP/SSE. The MCP bridge remains an external service: install and run it on a machine you control, then make its endpoint reachable from the ARIA container. Do not expose that endpoint to an untrusted network.

## Add a server

1. Open **Settings → Connections → MCP servers** as an administrator.
2. Add a stable name, the bridge URL and the transport offered by the server (`sse` or `http`). Add authentication headers only when the server requires them; ARIA masks stored header values in the UI.
3. Leave **Trust this server** off initially. Read-only annotated tools run directly, while unannotated or mutating tools use ARIA's confirmation preview. Trusting a server deliberately allows all of its tools to run without that confirmation boundary.
4. Set a per-server **call timeout** appropriate for the workload. A Blender render or generator call may need more time than a small scene query, but an unbounded timeout makes failures harder to recover from.
5. Enable the server and MCP master switch, save, then use **Reconnect** to verify discovery and the read-only Tool count.

The URL depends on your Docker/network layout. A bridge on the Docker host is commonly reached through the platform's host-gateway name; use your own routable name instead of copying an address from another installation. ARIA does not bundle a Blender bridge and does not open firewall ports for it.

## Blender-specific notes

- The Blender MCP bridge and add-on run on the user's machine. Keep Blender open when the bridge requires it and verify the bridge independently before diagnosing ARIA.
- Tools that execute Python or mutate the scene require confirmation unless the whole server was explicitly trusted. The preview includes server, Tool, bounded arguments and submitted Python code where applicable.
- AI 3D/image generators exposed by a Blender add-on require the user's own provider account and paid API keys. Put those keys in the add-on or service that owns them, not in chat messages.
- Tool-result image vision is supported only with Claude-family models. Other models receive an honest text placeholder instead of image bytes.

## Provider settings for long jobs

Model capabilities and costs differ. For long Agent/Blender jobs, a practical starting point is **16000 maximum output tokens** and a **300 second model timeout**, then reduce or increase them based on the chosen provider, budget and observed work. A per-model temperature may be left empty when the model rejects that parameter; an explicit `0.0` remains valid.

LiteLLM proxy users do not need a compatibility workaround for `tool_choice=none`; ARIA omits that unsupported value. Provider calls, MCP calls and ARIA's asynchronous job budget are separate time limits.

## Upgrade from Alpha604

Back up config/data and Qdrant volumes before changing images. Existing configuration and persistent user data are reused by Alpha982; old SearXNG or Valkey containers are not removed automatically and can be removed manually after verification. Then open **Memories → Maintenance** and run **Clean up old learning collections** once per user. That action does not remove personal memories, facts, preferences, documents or recipe experience.

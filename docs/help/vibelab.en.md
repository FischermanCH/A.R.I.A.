# Vibe:Lab

Vibe:Lab brings coding agents, terminals and ARIA's main chat into one working view.

## Connections, agents and workspaces

A **connection** provides SSH access and the allowed folders. An **agent** combines that access with a working folder, agent type, and defaults for autonomy, model and budget. Two agents may use the same folder, for example one with Codex and another with Claude.

A **workspace** stores only an arrangement of up to four windows; it has no working folder of its own. Create, rename or delete one from the top bar and layout changes are saved automatically. Deleting a workspace does not delete its agents or their work data. Manage connections and agents at `/vibelab/projects`.

## Window types

- **LLM** shows the same active conversation as ARIA's main chat by default, including its history and memory. A particular conversation can be bound explicitly later.
- **Agent** works with the selected agent in its folder and is available to administrators.
- **Terminal** gives administrators a direct shell through the selected connection.

## Isolated work and approvals

Each agent run uses its own Git worktree. Changes reach the local working folder only after **Apply to working folder**, with no push. Review **Changes** first. **New run** starts with fresh context, while the composer continues the latest run by default.

L0 asks for approval for actions that write or execute. L1 permits tightly scoped work, L2 works more independently and L3 is the broadest available autonomy. ARIA's fixed safety rules always apply. An uncovered action displays **Approval required** close to the composer. **Continues** marks an existing run; `/cls` and `/clear` archive or clear the current window.

Uploads and runs remain attached to the agent. Vibe:Lab synchronises running state across open devices. If a host is unavailable, history remains intact; check the connection and use **Try again**.

If a run hangs → **Technical details** → **Copy**. The details contain run state but no secret credentials.

# Chat, Queue, and Confirmations

Updated: 2026-07-09

## Purpose

Chat is ARIA's workspace for questions, local context lookup, and controlled actions. ARIA should not only answer text; it should understand the goal, load context, plan an action when needed, apply guardrails, execute, and make the result inspectable.

## Prompt Queue

When ARIA is working, the composer stays active. New prompts are added to the queue and run sequentially afterwards.

You can:

- reorder waiting prompts
- edit them
- remove them

The queue belongs to the current browser tab. It is not a persistent task board and does not survive reloads or browser restarts.

## Cancelling the current request

The cancel button stops the current browser request. Read-only requests already sent to external systems may still finish server-side, but ARIA does not start a second queued item in parallel.

## Pending Confirmations

Actions with side effects or higher risk can require confirmation. ARIA shows these confirmation-required actions as their own visible queue item with status.

Available actions:

- **Run** executes the prepared action while the confirmation is still valid.
- **Plan again** puts the original prompt back into the queue or starts it again.
- **Discard** removes the pending confirmation.

Expired or invalid confirmations are not executed automatically. Plan the action again if you still want it.

## Reading Details

Under **Details**, ARIA can show:

- loaded sources from Memory, documents, or web search
- routing and Operator Trace lines
- planned capability, connection, and runtime boundary
- policy and guardrail decisions
- tokens, cost, and runtime

These details are especially useful when ARIA misunderstood a target or blocked an action.

## Exporting Chat

**Export chat** creates a Markdown export of the currently visible chat. The export includes user prompts, ARIA answers, token/cost/runtime badges, and all routing/debug/Operator Trace lines from Details, even when those details are collapsed in the browser.

ARIA first copies the export to the clipboard. If the browser blocks clipboard access, ARIA automatically downloads a `.md` file.

## Mobile and iOS

Chat uses a fixed mobile workspace with its own scrollable history. On iPhone/iPad, the composer, queue, and toolbox remain reachable. Long prompts and confirmation buttons may wrap so they are not clipped on narrow viewports.

## Useful update tests

- submit a second prompt while a long answer is running
- reorder two waiting prompts
- edit one waiting prompt and remove another
- plan a confirmation-required action without running it immediately
- export the chat and verify that Details/debug lines are included
- check the same flow on iPhone width

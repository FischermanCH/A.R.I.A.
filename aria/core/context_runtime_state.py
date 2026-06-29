from __future__ import annotations

from typing import Any, MutableMapping

from aria.core.aria_turn_arbitration import AriaTurnArbitration
from aria.core.context_surfaces import TurnFrame


def turn_frame_from_arbitration(arbitration: AriaTurnArbitration | None) -> TurnFrame:
    if arbitration is None or not arbitration.plan.needs_context:
        return TurnFrame()
    plan = arbitration.plan
    request = next(iter(plan.context_requests), None)
    surface_id = request.surface_id if request is not None else (next(iter(plan.context_directions), "") or next(iter(plan.surfaces), ""))
    mode = request.mode if request is not None else ("inventory" if "context_inventory" in plan.intents else "search")
    topic = request.query if request is not None else ""
    if not topic:
        topic = next((str(value or "").strip() for value in plan.queries.values() if str(value or "").strip()), "")
    if not topic:
        topic = plan.reason
    return TurnFrame(
        surface_id=surface_id,
        mode=mode,
        topic=topic,
        catalog_ids=plan.priority,
        evidence_policy=plan.evidence_policy or ("source_bound" if plan.needs_context else ""),
        answer_mode=plan.answer_mode,
        source_scope="registered_context_surface",
        answer_contract="answer_only_from_selected_loaded_context",
        confidence=plan.confidence,
    )


class ContextRuntimeState:
    def __init__(self, frames: MutableMapping[str, TurnFrame]) -> None:
        self._frames = frames

    @staticmethod
    def user_key(user_id: str) -> str:
        return str(user_id or "web")

    def last_frame_payload(self, user_id: str) -> dict[str, Any]:
        frame = self._frames.get(self.user_key(user_id))
        return frame.as_payload() if frame is not None else {}

    def remember_frame(self, arbitration: AriaTurnArbitration | None, *, user_id: str) -> TurnFrame:
        frame = turn_frame_from_arbitration(arbitration)
        if frame.as_payload():
            self._frames[self.user_key(user_id)] = frame
        return frame

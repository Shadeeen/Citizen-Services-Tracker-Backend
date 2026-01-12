from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from app.models.service_requests import TransitionRequest


ALLOWED_TRANSITIONS = {
    "new": ["triaged"],
    "triaged": ["assigned"],
    "assigned": ["in_progress"],
    "in_progress": ["resolved"],
    "resolved": ["closed"],
    "closed": [],
}

TRANSITION_RULES_VERSION = "v1.0"


def get_allowed_next(state: str) -> List[str]:
    return ALLOWED_TRANSITIONS.get(state, [])


def validate_transition(current_state: str, request: TransitionRequest) -> None:
    allowed = get_allowed_next(current_state)
    if request.target_state not in allowed:
        raise ValueError(
            f"Invalid transition from {current_state} to {request.target_state}"
        )
    if request.target_state == "assigned" and not request.assigned_agent_id:
        raise ValueError("assigned_agent_id is required for assigned state")


def apply_transition_updates(
    current_state: str, transition: TransitionRequest
) -> Dict[str, Dict[str, object]]:
    now = datetime.utcnow()
    updates: Dict[str, Dict[str, object]] = {
        "$set": {
            "status": transition.target_state,
            "workflow.current_state": transition.target_state,
            "workflow.allowed_next": get_allowed_next(transition.target_state),
            "workflow.transition_rules_version": TRANSITION_RULES_VERSION,
            "timestamps.updated_at": now,
        }
    }
    if transition.target_state == "triaged":
        updates["$set"]["timestamps.triaged_at"] = now
    if transition.target_state == "assigned":
        updates["$set"]["timestamps.assigned_at"] = now
        updates["$set"]["assignment.assigned_agent_id"] = transition.assigned_agent_id
    if transition.target_state == "in_progress":
        updates["$set"]["timestamps.in_progress_at"] = now
    if transition.target_state == "resolved":
        updates["$set"]["timestamps.resolved_at"] = now
    if transition.target_state == "closed":
        updates["$set"]["timestamps.closed_at"] = now
    return updates

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import APIRouter, Header, HTTPException, Query

from app.models.service_requests import (
    CommentRequest,
    ServiceRequest,
    ServiceRequestCreate,
    TransitionRequest,
)
# from app.repositories.performance_logs import PerformanceLogRepository
from app.repositories.requests import ServiceRequestRepository
# from app.services.assignment import select_agent
# from app.services.requests import create_request
from app.services.workflow import apply_transition_updates, validate_transition

router = APIRouter(prefix="/requests", tags=["requests"])


@router.get("/", response_model=list[ServiceRequest])
async def list_requests(
    status: Optional[str] = Query(None, regex="^(new|triaged|assigned|in_progress|resolved|closed)$"),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ServiceRequest]:
    filters: Dict[str, Any] = {}
    if status:
        filters["status"] = status
    if category:
        filters["category"] = category
    documents = await ServiceRequestRepository.list_requests(filters, limit, offset)
    return [ServiceRequest(**doc) for doc in documents]


@router.post("/", response_model=ServiceRequest)
async def create_service_request(
    payload: ServiceRequestCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> ServiceRequest:
    document = await create_request(payload.dict(), idempotency_key)
    return ServiceRequest(**document)


@router.get("/{request_id}", response_model=ServiceRequest)
async def get_service_request(request_id: str) -> ServiceRequest:
    document = await ServiceRequestRepository.find_by_request_id(request_id)
    if not document:
        raise HTTPException(status_code=404, detail="Request not found")
    return ServiceRequest(**document)


@router.patch("/{request_id}/transition", response_model=ServiceRequest)
async def transition_request(
    request_id: str,
    payload: TransitionRequest,
) -> ServiceRequest:
    document = await ServiceRequestRepository.find_by_request_id(request_id)
    if not document:
        raise HTTPException(status_code=404, detail="Request not found")
    try:
        validate_transition(document["status"], payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updates = apply_transition_updates(document["status"], payload)
    updated = await ServiceRequestRepository.update_by_request_id(request_id, updates)
    await PerformanceLogRepository.append_event(
        updated["_id"],
        {
            "type": "transition",
            "by": {"actor_type": "system", "actor_id": "cst"},
            "at": datetime.utcnow(),
            "meta": {
                "from": document["status"],
                "to": payload.target_state,
                "note": payload.note,
            },
        },
    )
    if payload.target_state in {"resolved", "closed"}:
        created_at = updated["timestamps"]["created_at"]
        resolved_at = updated["timestamps"].get("resolved_at") or datetime.utcnow()
        resolution_minutes = (resolved_at - created_at).total_seconds() / 60
        performance_log = await PerformanceLogRepository.get_by_request_oid(
            updated["_id"]
        )
        kpis = performance_log["computed_kpis"] if performance_log else {}
        kpis.update(
            {
                "resolution_minutes": resolution_minutes,
                "sla_target_hours": updated["sla_policy"]["target_hours"],
            }
        )
        await PerformanceLogRepository.update_kpis(updated["_id"], kpis)
    return ServiceRequest(**updated)


@router.post("/{request_id}/auto-assign", response_model=ServiceRequest)
async def auto_assign_request(request_id: str) -> ServiceRequest:
    document = await ServiceRequestRepository.find_by_request_id(request_id)
    if not document:
        raise HTTPException(status_code=404, detail="Request not found")
    if document["status"] not in {"triaged", "assigned"}:
        raise HTTPException(status_code=400, detail="Request not ready for assignment")

    agent, candidates = await select_agent(
        document["location"]["zone_id"], document["category"]
    )
    if not agent:
        raise HTTPException(status_code=404, detail="No eligible agents found")

    updates: Dict[str, Any] = {
        "$set": {
            "assignment.assigned_agent_id": agent["_id"],
            "assignment.auto_assign_candidate_agents": [ObjectId(cid) for cid in candidates],
            "assignment.assignment_policy": "zone+skill+workload",
            "timestamps.updated_at": datetime.utcnow(),
        }
    }
    if document["status"] == "triaged":
        updates["$set"]["status"] = "assigned"
        updates["$set"]["workflow.current_state"] = "assigned"
        updates["$set"]["workflow.allowed_next"] = ["in_progress"]
        updates["$set"]["timestamps.assigned_at"] = datetime.utcnow()

    updated = await ServiceRequestRepository.update_by_request_id(request_id, updates)
    await PerformanceLogRepository.append_event(
        updated["_id"],
        {
            "type": "auto_assigned",
            "by": {"actor_type": "system", "actor_id": "cst"},
            "at": datetime.utcnow(),
            "meta": {"agent_id": str(agent["_id"]), "candidates": candidates},
        },
    )
    return ServiceRequest(**updated)


@router.post("/{request_id}/rating")
async def submit_rating(
    request_id: str,
    rating: float = Query(..., ge=1, le=5),
    dispute_flag: bool = Query(False),
    comment: Optional[str] = Query(None),
    reason_codes: Optional[str] = Query(None),
) -> Dict[str, Any]:
    document = await ServiceRequestRepository.find_by_request_id(request_id)
    if not document:
        raise HTTPException(status_code=404, detail="Request not found")
    feedback = {
        "rating": rating,
        "reason_codes": reason_codes.split(",") if reason_codes else [],
        "comment": comment,
        "dispute_flag": dispute_flag,
    }
    await PerformanceLogRepository.update_feedback(document["_id"], feedback)
    await PerformanceLogRepository.append_event(
        document["_id"],
        {
            "type": "rating",
            "by": {"actor_type": "citizen", "actor_id": "anonymous"},
            "at": datetime.utcnow(),
            "meta": feedback,
        },
    )
    return {"status": "ok"}


@router.post("/{request_id}/comment")
async def add_comment(
    request_id: str,
    payload: CommentRequest,
) -> Dict[str, Any]:
    document = await ServiceRequestRepository.find_by_request_id(request_id)
    if not document:
        raise HTTPException(status_code=404, detail="Request not found")
    await PerformanceLogRepository.append_event(
        document["_id"],
        {
            "type": "comment",
            "by": {"actor_type": "citizen", "actor_id": "anonymous"},
            "at": datetime.utcnow(),
            "meta": payload.dict(),
        },
    )
    return {"status": "ok"}


@router.post("/{request_id}/escalate")
async def manual_escalate(request_id: str) -> Dict[str, Any]:
    document = await ServiceRequestRepository.find_by_request_id(request_id)
    if not document:
        raise HTTPException(status_code=404, detail="Request not found")
    performance_log = await PerformanceLogRepository.get_by_request_oid(document["_id"])
    kpis = performance_log["computed_kpis"] if performance_log else {}
    escalation_count = kpis.get("escalation_count", 0) + 1
    kpis["escalation_count"] = escalation_count
    await PerformanceLogRepository.update_kpis(document["_id"], kpis)
    await PerformanceLogRepository.append_event(
        document["_id"],
        {
            "type": "manual_escalation",
            "by": {"actor_type": "staff", "actor_id": "manual"},
            "at": datetime.utcnow(),
            "meta": {"escalation_count": escalation_count},
        },
    )
    return {"status": "ok", "escalation_count": escalation_count}

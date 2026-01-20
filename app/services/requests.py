from datetime import datetime
from typing import Optional

from app.db.mongo import requests_collection, audit_collection
from app.models.service_requests import (
    ServiceRequest,
    ServiceRequestCreate,
    ServiceRequestUpdate,
)
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService

audit_repo = AuditRepository(audit_collection)
audit_service = AuditService(audit_repo)


# ------------------------------------------------------------------
# Create request (status = NEW)
# ------------------------------------------------------------------
async def create_request(data: ServiceRequestCreate) -> dict:
    now = datetime.utcnow()

    doc = {
        "request_id": f"REQ-{int(now.timestamp())}",
        "citizen_ref": data.citizen_ref.dict(),
        "category": data.category,
        "sub_category": data.sub_category,
        "description": data.description,
        "tags": data.tags,
        "status": "new",
        "priority": "P3",

        "workflow": {
            "current_state": "new",
            "allowed_next": ["triaged"],
            "transition_rules_version": "v1",
        },

        "sla_policy": None,

        "timestamps": {
            "created_at": now,
            "updated_at": now,
            "triaged_at": None,
            "assigned_at": None,
            "in_progress_at": None,
            "resolved_at": None,
            "closed_at": None,
        },

        "location": {
            "type": "Point",
            "coordinates": data.location.coordinates,
            "address_hint": data.location.address_hint,
            "zone_id": "UNKNOWN",
        },

        "duplicates": {
            "is_master": True,
            "linked_duplicates": [],
        },

        "assignment": {
            "assigned_agent_id": None,
            "auto_assign_candidate_agents": [],
            "assignment_policy": None,
        },

        "evidence": [e.dict() for e in data.evidence],
        "internal": {
            "notes": data.internal_notes,
            "visibility": "internal_only",
        },
    }

    res = await requests_collection.insert_one(doc)
    doc["_id"] = res.inserted_id

    await audit_service.log_event({
        "time": now,
        "type": "request.create",
        "actor": {"role": "system"},
        "entity": {"type": "request", "id": doc["request_id"]},
        "message": "Service request created",
        "meta": {},
    })

    return doc


# ------------------------------------------------------------------
# Get request by ID
# ------------------------------------------------------------------
async def get_request_by_id(request_id: str) -> Optional[dict]:
    return await requests_collection.find_one({"request_id": request_id})


# ------------------------------------------------------------------
# Update request (SAFE fields only)
# ------------------------------------------------------------------
async def update_request(
    request_id: str,
    patch: ServiceRequestUpdate,
    actor: dict,
) -> Optional[dict]:

    update = patch.dict(exclude_unset=True)
    if not update:
        return await get_request_by_id(request_id)

    update["timestamps.updated_at"] = datetime.utcnow()

    res = await requests_collection.update_one(
        {"request_id": request_id},
        {"$set": update},
    )

    if res.matched_count != 1:
        return None

    doc = await get_request_by_id(request_id)

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "request.update",
        "actor": actor,
        "entity": {"type": "request", "id": request_id},
        "message": "Request updated",
        "meta": update,
    })

    return doc


# ------------------------------------------------------------------
# TRIAGE request (INTERNAL – used ONLY by SLA service)
# ------------------------------------------------------------------
async def mark_request_triaged(
    request_id: str,
    sla_id,
    team_id,
    actor: dict,
) -> dict:
    now = datetime.utcnow()

    res = await requests_collection.update_one(
        {
            "request_id": request_id,
            "status": "new",  # enforce rule
        },
        {
            "$set": {
                "status": "triaged",
                "workflow.current_state": "triaged",
                "workflow.allowed_next": ["assigned"],
                "sla_policy": sla_id,
                "assignment.assignment_policy": str(team_id),
                "timestamps.triaged_at": now,
                "timestamps.updated_at": now,
            }
        },
    )

    if res.matched_count != 1:
        raise ValueError("Request is not in NEW state")

    await audit_service.log_event({
        "time": now,
        "type": "request.triaged",
        "actor": actor,
        "entity": {"type": "request", "id": request_id},
        "message": "Request triaged via SLA creation",
        "meta": {
            "sla_id": str(sla_id),
            "team_id": str(team_id),
        },
    })

    return await get_request_by_id(request_id)

from datetime import datetime
from bson import ObjectId

from app.db.mongo import sla_collection, audit_collection
from app.models.sla_policy import SLAPolicyCreate, SLAPolicyUpdate
from app.services.requests import mark_request_triaged
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService

audit_repo = AuditRepository(audit_collection)
audit_service = AuditService(audit_repo)


# -------------------------------------------------------------------
# Create SLA for request → TRIAGES request
# -------------------------------------------------------------------
async def create_sla_for_request(data: SLAPolicyCreate, actor: dict):
    now = datetime.utcnow()

    # 1️⃣ Build SLA document
    sla_doc = {
        "request_id": data.request_id,
        "team_id": data.team_id,

        "name": data.name,
        "zone": data.zone,
        "priority": data.priority,
        "category_code": data.category_code,
        "subcategory_code": data.subcategory_code,

        "target_hours": data.target_hours,
        "breach_threshold_hours": data.breach_threshold_hours,
        "escalation_steps": data.escalation_steps,

        "active": True,
        "created_at": now,
        "updated_at": now,
    }

    # 2️⃣ Insert SLA
    res = await sla_collection.insert_one(sla_doc)
    sla_id = res.inserted_id

    # 3️⃣ TRIAGE request via service (single source of truth)
    await mark_request_triaged(
        request_id=data.request_id,
        sla_id=sla_id,
        team_id=data.team_id,
        actor=actor,
    )

    # 4️⃣ Audit
    await audit_service.log_event({
        "time": now,
        "type": "sla.created",
        "actor": actor,
        "entity": {
            "type": "sla",
            "id": str(sla_id),
        },
        "message": "SLA created and request triaged",
        "meta": {
            "request_id": data.request_id,
            "team_id": str(data.team_id),
        },
    })

    sla_doc["_id"] = sla_id
    return sla_doc


# -------------------------------------------------------------------
# Update SLA (allowed only for existing SLA)
# -------------------------------------------------------------------
async def update_sla(sla_id: str, patch: SLAPolicyUpdate, actor: dict):
    try:
        oid = ObjectId(sla_id)
    except Exception:
        raise ValueError("Invalid SLA ID")

    update = patch.dict(exclude_unset=True)
    if not update:
        return await sla_collection.find_one({"_id": oid})

    update["updated_at"] = datetime.utcnow()

    res = await sla_collection.update_one(
        {"_id": oid},
        {"$set": update},
    )

    if res.matched_count != 1:
        return None

    doc = await sla_collection.find_one({"_id": oid})

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "sla.updated",
        "actor": actor,
        "entity": {
            "type": "sla",
            "id": sla_id,
        },
        "message": "SLA updated",
        "meta": update,
    })

    return doc


# -------------------------------------------------------------------
# Get SLA by request
# -------------------------------------------------------------------
async def get_sla_by_request(request_id: str):
    return await sla_collection.find_one({"request_id": request_id})

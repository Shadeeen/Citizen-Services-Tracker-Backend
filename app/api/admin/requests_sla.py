from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.db.mongo import requests_collection, sla_rules_collection, subcategory_collection, team_collection
from app.models.sla_policy import SLAPolicyCreate, SLAPolicyUpdate
from bson import ObjectId

from app.utils.mongo import serialize_mongo
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService
from app.db.mongo import audit_collection

audit_service = AuditService(AuditRepository(audit_collection))

router = APIRouter(
    prefix="/admin/requests",
    tags=["Admin Request SLA"]
)



@router.post("/{request_id}/sla")
async def create_sla(request_id: str, payload: dict):
    req = await requests_collection.find_one({"request_id": request_id})
    if not req:
        raise HTTPException(404, "Request not found")

    # 1️⃣ Extract request data
    zone = req["zone_name"]
    category = req["category"]
    subcategory = req["sub_category"]

    # 2️⃣ Load subcategory → priority
    sub = await subcategory_collection.find_one({"name": subcategory})
    if not sub:
        raise HTTPException(400, "Invalid subcategory")

    priority = sub["priority"]

    # 3️⃣ Load SLA rules
    rules = await sla_rules_collection.find_one()
    zone_hours = rules["zones"].get(zone)
    priority_hours = rules["priorities"].get(priority)

    if zone_hours is None or priority_hours is None:
        raise HTTPException(400, "Missing SLA rules")

    target_hours = zone_hours + priority_hours

    if "team_id" not in payload:
        raise HTTPException(400, "team_id is required")

    team = await team_collection.find_one({
        "_id": ObjectId(payload["team_id"]),
        "deleted": False,
        "active": True
    })

    if not team:
        raise HTTPException(
            status_code=400,
            detail="Assigned team not found"
        )

    team_zones = team.get("zones", [])

    # ✅ allow teams that support all zones
    if team_zones and zone not in team_zones:
        raise HTTPException(
            status_code=400,
            detail="Team does not support this zone"
        )
    # 5️⃣ Build SLA
    sla = SLAPolicyCreate(
        request_id=request_id,
        name=f"SLA for {request_id}",
        zone=zone,
        priority=priority,
        category_code=category,
        subcategory_code=subcategory,
        target_hours=target_hours,
        breach_threshold_hours=payload.get("breach_threshold_hours", target_hours),
        team_id=payload["team_id"],  # ✅ FIXED
        escalation_steps=payload.get("escalation_steps", [])
    )

    # 6️⃣ Save SLA on request
    await requests_collection.update_one(
        {"request_id": request_id},
        {
            "$set": {
                "sla_policy": sla.model_dump(),
                "status": "triaged",
                "timestamps.triaged_at": datetime.utcnow()
            }
        }
    )

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "sla.create",
        "actor": {
            "role": "admin",
            "email": "admin@system"
        },
        "entity": {
            "type": "request",
            "id": request_id
        },
        "message": f"SLA created for request {request_id}",
        "meta": {
            "sla": sla.model_dump(),
            "team": {
                "id": payload["team_id"],
                "name": team.get("name"),
                "zones": team.get("zones", [])
            }
        }
    })

    return {"ok": True}

@router.put("/{request_id}/sla")
async def update_sla(request_id: str, payload: SLAPolicyUpdate):

    req = await requests_collection.find_one({"request_id": request_id})

    if not req or "sla_policy" not in req:
        raise HTTPException(status_code=404, detail="SLA not found")

    if req.get("status") != "triaged":
        raise HTTPException(
            status_code=403,
            detail="SLA can only be edited while request is triaged"
        )

    before = req["sla_policy"]
    updates = payload.dict(exclude_unset=True)

    await requests_collection.update_one(
        {"request_id": request_id},
        {"$set": {"sla_policy": {**before, **updates}}}
    )

    changes = {
        k: {
            "from": before.get(k),
            "to": updates[k]
        }
        for k in updates
        if before.get(k) != updates[k]
    }

    if changes:
        await audit_service.log_event({
            "time": datetime.utcnow(),
            "type": "sla.update",
            "actor": {
                "role": "admin",
                "email": "admin@system"
            },
            "entity": {
                "type": "request",
                "id": request_id
            },
            "message": f"SLA updated for request {request_id}",
            "meta": {
                "changes": changes
            }
        })

    return {"ok": True}


@router.get("/{request_id}/sla")
async def get_sla(request_id: str):
    req = await requests_collection.find_one({"request_id": request_id})
    if not req or "sla_policy" not in req:
        raise HTTPException(status_code=404, detail="SLA not found")

    # 🔥 THIS IS THE ONLY SAFE WAY
    return serialize_mongo(req["sla_policy"])


@router.get("/{request_id}/sla/teams")
async def get_sla_teams(request_id: str):
    req = await requests_collection.find_one({"request_id": request_id})
    if not req:
        raise HTTPException(404, "Request not found")

    zone = req["zone_name"]

    teams = await team_collection.find(
        {
            "deleted": False,
            "active": True,   # ✅ THIS IS THE ONLY ADDITION
            "$or": [
                {"zones": {"$size": 0}},  # teams that work in all zones
                {"zones": zone}           # teams that work in this zone
            ]
        }
    ).to_list(None)

    return [
        {
            "id": str(t["_id"]),
            "name": t["name"],
            "zones": t.get("zones", [])
        }
        for t in teams
    ]

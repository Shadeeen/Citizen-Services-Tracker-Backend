from fastapi import APIRouter, HTTPException
from datetime import datetime

from app.db.mongo import requests_collection, sla_rules_collection, subcategory_collection, team_collection
from app.models.sla_policy import SLAPolicyCreate

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

    # 4️⃣ Validate team
    team = await team_collection.find_one({
        "_id": payload["assigned_team_id"],
        "zones": zone
    })
    if not team:
        raise HTTPException(400, "Team does not support this zone")

    # 5️⃣ Build SLA
    sla = SLAPolicyCreate(
        name=f"SLA for {request_id}",
        zone=zone,
        priority=priority,
        category=category,
        subcategory=subcategory,
        target_hours=target_hours,
        breach_hours=payload.get("breach_hours", target_hours),
        assigned_team_id=payload["assigned_team_id"],
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

    return {"ok": True}


@router.put("/{request_id}/sla")
async def update_sla(request_id: str, payload: SLAPolicyCreate):

    req = await requests_collection.find_one({"request_id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if "sla_policy" not in req:
        raise HTTPException(status_code=404, detail="SLA not found")

    await requests_collection.update_one(
        {"request_id": request_id},
        {
            "$set": {
                "sla_policy": payload.dict()
            }
        }
    )

    return {"ok": True}


@router.get("/{request_id}/sla", response_model=SLAPolicyCreate)
async def get_sla(request_id: str):
    req = await requests_collection.find_one({"request_id": request_id})
    if not req or "sla_policy" not in req:
        raise HTTPException(404, "SLA not found")
    return req["sla_policy"]


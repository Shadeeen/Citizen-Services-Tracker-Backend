
from fastapi import APIRouter, HTTPException
from datetime import datetime
from bson import ObjectId

from app.db.mongo import (
    requests_collection,
    sla_rules_collection,
    subcategory_collection,
    team_collection,
    audit_collection,
)
from app.models.sla_policy import SLAPolicyCreate, SLAPolicyUpdate
from app.utils.mongo import serialize_mongo
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService

audit_service = AuditService(AuditRepository(audit_collection))

router = APIRouter(prefix="/admin/requests", tags=["Admin Request SLA"])


# ----------------------------- helpers -----------------------------

def _normalize_team_id(raw):
    """
    Frontend sends team_id as:
    - "" (when not selected)
    - "64f..." (string ObjectId)
    This converts "" / None -> None, otherwise returns string.
    """
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip() == "":
        return None
    return str(raw)


async def _validate_team_for_zone(team_id_str: str, zone: str):
    """
    Validates team exists, active, not deleted, and supports the zone.
    Returns team document + ObjectId.
    """
    try:
        oid = ObjectId(team_id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid team_id")

    team = await team_collection.find_one({"_id": oid, "deleted": False, "active": True})
    if not team:
        raise HTTPException(status_code=400, detail="Assigned team not found")

    team_zones = team.get("zones", [])
    # allow teams that support all zones (zones == [])
    if team_zones and zone not in team_zones:
        raise HTTPException(status_code=400, detail="Team does not support this zone")

    return team, oid


# -------------------------------------------------------------------
# Create SLA (team optional) -> TRIAGED
# -------------------------------------------------------------------
@router.post("/{request_id}/sla")
async def create_sla(request_id: str, payload: dict):
    req = await requests_collection.find_one({"request_id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    zone = req["zone_name"]
    category = req["category"]
    subcategory = req["sub_category"]

    sub = await subcategory_collection.find_one({"name": subcategory})
    if not sub:
        raise HTTPException(status_code=400, detail="Invalid subcategory")

    priority = sub["priority"]

    rules = await sla_rules_collection.find_one()
    if not rules:
        raise HTTPException(status_code=400, detail="Missing SLA rules")

    zone_hours = rules.get("zones", {}).get(zone)
    priority_hours = rules.get("priorities", {}).get(priority)
    if zone_hours is None or priority_hours is None:
        raise HTTPException(status_code=400, detail="Missing SLA rules")

    target_hours = zone_hours + priority_hours

    # ✅ team_id is OPTIONAL (frontend might send "" -> normalize to None)
    team_id_str = _normalize_team_id(payload.get("team_id"))
    team = None
    team_oid = None
    if team_id_str:
        team, team_oid = await _validate_team_for_zone(team_id_str, zone)

    sla = SLAPolicyCreate(
        request_id=request_id,
        name=f"SLA for {request_id}",
        zone=zone,
        priority=priority,
        category_code=category,
        subcategory_code=subcategory,
        target_hours=target_hours,
        breach_threshold_hours=payload.get("breach_threshold_hours", target_hours),
        team_id=team_oid,  # ✅ ObjectId or None (won't break serialize_mongo)
        escalation_steps=payload.get("escalation_steps", []),
    )

    # Always TRIAGED on create
    await requests_collection.update_one(
        {"request_id": request_id},
        {
            "$set": {
                "sla_policy": sla.model_dump(by_alias=True),
                "status": "triaged",
                "timestamps.triaged_at": datetime.utcnow(),
            }
        },
    )

    meta = {"sla": sla.model_dump(by_alias=True)}
    if team:
        meta["team"] = {
            "id": str(team["_id"]),
            "name": team.get("name"),
            "zones": team.get("zones", []),
        }

    await audit_service.log_event(
        {
            "time": datetime.utcnow(),
            "type": "sla.create",
            "actor": {"role": "admin", "email": "admin@system"},
            "entity": {"type": "request", "id": request_id},
            "message": f"SLA created for request {request_id}",
            "meta": meta,
        }
    )

    return {"ok": True}


@router.put("/{request_id}/sla")
async def update_sla(request_id: str, payload: SLAPolicyUpdate):
    req = await requests_collection.find_one({"request_id": request_id})
    if not req or "sla_policy" not in req:
        raise HTTPException(status_code=404, detail="SLA not found")

    if req.get("status") == "closed":
        raise HTTPException(status_code=403, detail="Cannot edit SLA when request is closed")

    status = req.get("status")
    before = req["sla_policy"]
    updates = payload.dict(exclude_unset=True)

    if not updates:
        return {"ok": True}

    # -------------------------
    # Team update rules
    # -------------------------
    if "team_id" in updates:
        incoming_team_str = _normalize_team_id(updates.get("team_id"))

        current_team = before.get("team_id")
        current_team_str = str(current_team) if current_team else None

        # If no actual change -> ok in any status
        if incoming_team_str == current_team_str:
            updates["team_id"] = current_team  # keep as ObjectId/None
        else:
            # Only allow changing team when status is EXACTLY "assigned"
            if status != "assigned":
                raise HTTPException(
                    status_code=403,
                    detail="Team cant changed while request is in_progress",
                )

            # status == assigned => validate and store as ObjectId (or allow clearing)
            if incoming_team_str is None:
                updates["team_id"] = None
            else:
                zone = req.get("zone_name")
                team, team_oid = await _validate_team_for_zone(incoming_team_str, zone)
                updates["team_id"] = team_oid

    # merge SLA updates
    new_sla = {**before, **updates}
    set_doc = {"sla_policy": new_sla}

    # (Optional) if you want to track reassignment time:
    if status == "assigned" and "team_id" in updates and str(before.get("team_id")) != str(new_sla.get("team_id")):
        set_doc["timestamps.reassigned_at"] = datetime.utcnow()

    await requests_collection.update_one({"request_id": request_id}, {"$set": set_doc})

    # audit changes
    changes = {
        k: {"from": before.get(k), "to": new_sla.get(k)}
        for k in updates
        if str(before.get(k)) != str(new_sla.get(k))
    }

    if changes:
        await audit_service.log_event(
            {
                "time": datetime.utcnow(),
                "type": "sla.update",
                "actor": {"role": "admin", "email": "admin@system"},
                "entity": {"type": "request", "id": request_id},
                "message": f"SLA updated for request {request_id}",
                "meta": {"changes": serialize_mongo(changes)},
            }
        )

    return {"ok": True}



# -------------------------------------------------------------------
# Get SLA
# -------------------------------------------------------------------
@router.get("/{request_id}/sla")
async def get_sla(request_id: str):
    req = await requests_collection.find_one({"request_id": request_id})
    if not req or "sla_policy" not in req:
        raise HTTPException(status_code=404, detail="SLA not found")

    return serialize_mongo(req["sla_policy"])


# -------------------------------------------------------------------
# Teams for this request zone
# -------------------------------------------------------------------
@router.get("/{request_id}/sla/teams")
async def get_sla_teams(request_id: str):
    req = await requests_collection.find_one({"request_id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    zone = req["zone_name"]

    teams = await team_collection.find(
        {
            "deleted": False,
            "active": True,
            "$or": [
                {"zones": {"$size": 0}},  # all zones
                {"zones": zone},          # this zone
            ],
        }
    ).to_list(None)

    return [
        {"id": str(t["_id"]), "name": t["name"], "zones": t.get("zones", [])}
        for t in teams
    ]

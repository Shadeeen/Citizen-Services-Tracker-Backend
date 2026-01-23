from fastapi import APIRouter, HTTPException
from datetime import datetime
from bson import ObjectId

from app.db.mongo import (
    requests_collection,
    sla_rules_collection,
    subcategory_collection,
    team_collection,
    audit_collection,
    performance_logs_collection,
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


def _dt(v):
    # normalize to datetime or None
    if isinstance(v, datetime):
        return v
    return None


def _now():
    return datetime.utcnow()


def _minutes_between(a: datetime, b: datetime) -> int:
    return int(max(0, (b - a).total_seconds() // 60))


def _hours_between(a: datetime, b: datetime) -> float:
    return max(0.0, (b - a).total_seconds() / 3600.0)


def _compute_sla_kpis(req_doc: dict, sla_policy: dict) -> dict:
    """
    Returns computed_kpis for performance_logs.
    Minimal + consistent fields you already expect in UI.
    """
    ts = (req_doc.get("timestamps") or {})
    created_at = _dt(ts.get("created_at")) or _dt(req_doc.get("created_at")) or _now()

    # SLA usually starts at triage (or created if missing)
    start_at = _dt(ts.get("triaged_at")) or created_at

    status = str(req_doc.get("status") or "").lower()
    end_at = None
    if status == "resolved":
        end_at = _dt(ts.get("resolved_at"))
    elif status == "closed":
        end_at = _dt(ts.get("closed_at")) or _dt(ts.get("updated_at"))

    current = end_at or _now()

    target_h = float(sla_policy.get("target_hours") or 0)
    breach_h = float(sla_policy.get("breach_threshold_hours") or target_h)

    elapsed_h = _hours_between(start_at, current)

    # Simple states (adjust if you want different logic)
    if breach_h > 0 and elapsed_h >= breach_h:
        sla_state = "breached"
    elif target_h > 0 and elapsed_h >= target_h:
        sla_state = "at_risk"
    else:
        sla_state = "on_track"

    resolution_minutes = None
    if end_at is not None:
        resolution_minutes = _minutes_between(start_at, end_at)

    return {
        "resolution_minutes": resolution_minutes,
        "sla_target_hours": target_h,
        "sla_state": sla_state,
        "escalation_count": int(sla_policy.get("escalation_count") or 0),
        "breach_reason": sla_policy.get("breach_reason"),  # keep if you set it later
        "computed_at": _now(),  # optional but useful
    }


async def _upsert_performance_log(req_doc: dict):
    """
    Ensures a performance_logs doc exists for this request, and updates computed_kpis.
    IMPORTANT: store request_id as ObjectId = req_doc["_id"] (your lookup uses that).
    """
    sla_policy = req_doc.get("sla_policy")
    if not sla_policy:
        return  # nothing to compute yet

    computed_kpis = _compute_sla_kpis(req_doc, sla_policy)

    await performance_logs_collection.update_one(
        {"request_id": req_doc["_id"]},  # ✅ ObjectId link
        {
            "$setOnInsert": {
                "request_id": req_doc["_id"],
                "event_stream": [],
                "created_at": _now(),
            },
            "$set": {
                "computed_kpis": computed_kpis,
                "updated_at": _now(),
            },
        },
        upsert=True,
    )


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

    now = datetime.utcnow()
    new_status = "assigned" if team_oid else "triaged"

    sla_dump = sla.model_dump(by_alias=True)
    sla_dump["team_id"] = team_oid  # keep in sync

    set_doc = {
        "sla_policy": sla_dump,
        "status": new_status,
        "timestamps.triaged_at": now,
        "assignment.assigned_team_id": team_oid,
    }

    update = {"$set": set_doc}

    if team_oid:
        update["$set"]["timestamps.assigned_at"] = now
    else:
        update["$unset"] = {"timestamps.assigned_at": ""}  # ✅ remove field

    await requests_collection.update_one({"request_id": request_id}, update)

    # ✅ recompute & upsert performance log
    req = await requests_collection.find_one({"request_id": request_id})
    await _upsert_performance_log(req)

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

    if req.get("status") == "resolved":
        raise HTTPException(status_code=403, detail="Cannot edit SLA when request is resolved")

    status = req.get("status")
    before = req["sla_policy"]
    updates = payload.dict(exclude_unset=True)

    if not updates:
        return {"ok": True}

    # -------------------------
    # Team update rules
    # -------------------------
    # -------------------------
    # Team update rules
    # -------------------------
    allowed_team_change_statuses = {"new", "assigned","triaged"}

    if "team_id" in updates:
        incoming_team_str = _normalize_team_id(updates.get("team_id"))

        current_team = before.get("team_id")
        current_team_str = str(current_team) if current_team else None

        # If no actual change -> keep as-is
        if incoming_team_str == current_team_str:
            updates["team_id"] = current_team
        else:
            # ✅ allow ONLY in new or assigned
            if status not in allowed_team_change_statuses:
                raise HTTPException(
                    status_code=403,
                    detail="Team can be changed only when request is new or assigned",
                )

            # Validate & convert (or clear)
            if incoming_team_str is None:
                updates["team_id"] = None
            else:
                zone = req.get("zone_name")
                team, team_oid = await _validate_team_for_zone(incoming_team_str, zone)
                updates["team_id"] = team_oid

    # merge SLA updates
    new_sla = {**before, **updates}

    set_doc = {"sla_policy": new_sla}

    # ✅ keep assignment in sync if team changed
    team_changed = (
            "team_id" in updates and str(before.get("team_id")) != str(new_sla.get("team_id"))
    )
    if team_changed:
        now = datetime.utcnow()

        new_team = new_sla.get("team_id")
        set_doc["assignment.assigned_team_id"] = new_team

        # ✅ keep request status consistent with create_sla behavior
        set_doc["status"] = "assigned" if new_team else "triaged"

        if new_team:
            # first assignment time if empty, otherwise reassignment
            if not (req.get("timestamps") or {}).get("assigned_at"):
                set_doc["timestamps.assigned_at"] = now
            else:
                set_doc["timestamps.reassigned_at"] = now
        else:
            # team cleared
            set_doc["timestamps.reassigned_at"] = now  # optional

    await requests_collection.update_one({"request_id": request_id}, {"$set": set_doc})

    # ✅ recompute & upsert performance log
    req = await requests_collection.find_one({"request_id": request_id})
    await _upsert_performance_log(req)
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
                {"zones": zone},  # this zone
            ],
        }
    ).to_list(None)

    return [
        {"id": str(t["_id"]), "name": t["name"], "zones": t.get("zones", [])}
        for t in teams
    ]

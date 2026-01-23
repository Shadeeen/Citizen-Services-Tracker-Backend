# app/api/service_requests.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Header, Request
from datetime import datetime
from bson import ObjectId
from pathlib import Path
import uuid
import os


from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

from app.db.mongo import service_requests_collection, db, users_collection, team_collection
from app.schemas.service_request import (
    CreateServiceRequestBody,
    CreateServiceRequestResponse,
    UpdateServiceRequestBody,
    CitizenFeedbackIn,
)
from app.db.mongo import audit_collection
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService

audit_service = AuditService(AuditRepository(audit_collection))

router = APIRouter(prefix="/service-requests", tags=["Service Requests"])

performance_logs_collection = db["performance_logs"]
counters_collection = db["counters"]


# -------------------------
# Helpers
# -------------------------

def _dt(v):
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except:
            return None
    return None


def _minutes_between(a: datetime, b: datetime) -> int:
    return int(max(0, (b - a).total_seconds() // 60))


def _hours_between(a: datetime, b: datetime) -> float:
    return max(0.0, (b - a).total_seconds() / 3600.0)


def _compute_kpis(sr: dict) -> dict:
    ts = sr.get("timestamps") or {}
    created_at = _dt(ts.get("created_at")) or _dt(sr.get("created_at")) or datetime.utcnow()
    triaged_at = _dt(ts.get("triaged_at")) or created_at

    status = (sr.get("status") or "").lower()
    end_at = None
    if status == "resolved":
        end_at = _dt(ts.get("resolved_at"))
    elif status == "closed":
        end_at = _dt(ts.get("closed_at")) or _dt(ts.get("updated_at"))

    now = datetime.utcnow()
    current = end_at or now

    sla_policy = sr.get("sla_policy") or {}
    target_h = float(sla_policy.get("target_hours") or 0)
    breach_h = float(sla_policy.get("breach_threshold_hours") or target_h)

    elapsed_h = _hours_between(triaged_at, current)

    if breach_h > 0 and elapsed_h >= breach_h:
        sla_state = "breached"
    elif target_h > 0 and elapsed_h >= target_h:
        sla_state = "at_risk"
    else:
        sla_state = "on_track"

    resolution_minutes = None
    if end_at is not None:
        resolution_minutes = _minutes_between(triaged_at, end_at)

    return {
        "resolution_minutes": resolution_minutes,
        "sla_target_hours": target_h,
        "sla_state": sla_state,
        "escalation_count": 0,
        "breach_reason": None,
        "computed_at": now,
    }


async def _upsert_perf_log(sr: dict):
    sr_oid = sr["_id"]
    now = datetime.utcnow()
    kpis = _compute_kpis(sr)

    await performance_logs_collection.update_one(
        {"request_id": sr_oid},
        {
            "$setOnInsert": {
                "request_id": sr_oid,
                "event_stream": [],
                "created_at": now,
            },
            "$set": {
                "computed_kpis": kpis,
                "updated_at": now,
            },
        },
        upsert=True,
    )


def _make_request_id(year: int, seq: int) -> str:
    return f"CST-{year}-{seq:04d}"


def _parse_citizen_id(x_citizen_id: str | None) -> ObjectId | None:
    if not x_citizen_id:
        return None
    x_citizen_id = x_citizen_id.strip()
    if not ObjectId.is_valid(x_citizen_id):
        return None
    return ObjectId(x_citizen_id)


def _parse_oid(x: str | None) -> ObjectId | None:
    if not x:
        return None
    x = x.strip()
    if not ObjectId.is_valid(x):
        return None
    return ObjectId(x)


async def _next_seq_for_year(year: int) -> int:
    """
    Atomic counter per year:
    counters: { _id: "service_requests_2026", seq: 4 }
    """
    key = f"service_requests_{year}"
    doc = await counters_collection.find_one_and_update(
        {"_id": key},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return int(doc["seq"])


async def _sync_counter_to_latest(year: int) -> int:
    """
    Self-healing:
    If counters is behind existing requests, sync it to the latest seq found in DB.
    Returns the max_seq it synced to.
    """
    last = await service_requests_collection.find_one(
        {"request_id": {"$regex": f"^CST-{year}-"}},
        sort=[("request_id", -1)]
    )

    max_seq = 0
    if last and last.get("request_id"):
        try:
            max_seq = int(last["request_id"].split("-")[-1])
        except:
            max_seq = 0

    key = f"service_requests_{year}"
    await counters_collection.update_one(
        {"_id": key},
        {"$set": {"seq": max_seq}},
        upsert=True
    )
    return max_seq


async def _assert_staff_or_403(x_staff_id: str | None) -> ObjectId:
    staff_oid = _parse_oid(x_staff_id)
    if staff_oid is None:
        raise HTTPException(403, "Missing/invalid X-Staff-Id")

    u = await users_collection.find_one({"_id": staff_oid})
    if not u or (u.get("role") or "").lower() != "staff":
        raise HTTPException(403, "Not staff")

    return staff_oid


def _assert_owner_or_403(doc: dict, citizen_oid: ObjectId | None):
    anonymous = doc.get("citizen_ref", {}).get("anonymous", False)
    stored = doc.get("citizen_ref", {}).get("citizen_id", None)

    if anonymous:
        raise HTTPException(403, "Anonymous requests are not allowed for this action")
    if citizen_oid is None or stored != citizen_oid:
        raise HTTPException(403, "Not allowed")


async def _ensure_performance_log_exists(service_request_doc: dict):
    """
    Create performance log ONLY when request is CLOSED,
    but if it doesn't exist, create it now.
    """
    sr_oid = service_request_doc["_id"]

    exists = await performance_logs_collection.find_one({"request_id": sr_oid})
    if exists:
        return

    now = datetime.utcnow()

    await performance_logs_collection.insert_one({
        "request_id": sr_oid,
        "event_stream": [
            {"type": "log_created", "at": now}
        ],
        "computed_kpis": {
            "resolution_minutes": None,
            "sla_target_hours": 48,
            "sla_state": "on_track",
            "escalation_count": 0,
            "breach_reason": None,
            "citizen_feedback": None
        }
    })


def _actor_from_request(doc: dict, citizen_oid: ObjectId | None):
    anonymous = doc.get("citizen_ref", {}).get("anonymous", False)

    if anonymous:
        return {"role": "anonymous", "email": "anonymous@system"}

    stored = doc.get("citizen_ref", {}).get("citizen_id")
    same_owner = (citizen_oid is not None and stored == citizen_oid)

    return {
        "role": "citizen",
        "email": "citizen@system",
        "citizen_id": str(stored) if stored else None,
        "verified_owner": same_owner
    }


# =========================
# Create Service Request
# =========================
@router.post("", response_model=CreateServiceRequestResponse)
async def create_service_request(body: CreateServiceRequestBody):
    now = datetime.utcnow()
    year = now.year

    citizen_id = None
    if not body.citizen_ref.anonymous:
        if body.citizen_ref.citizen_id:
            if not ObjectId.is_valid(body.citizen_ref.citizen_id):
                raise HTTPException(400, "Invalid citizen_id")
            citizen_id = ObjectId(body.citizen_ref.citizen_id)
        else:
            raise HTTPException(400, "citizen_id is required when anonymous=false")

    doc_base = {
        "citizen_ref": {
            "citizen_id": citizen_id,
            "anonymous": body.citizen_ref.anonymous,
            "contact_channel": body.citizen_ref.contact_channel
        },
        "category": body.category,
        "sub_category": body.sub_category,
        "description": body.description,
        "tags": body.tags or [],
        "status": "new",
        "priority": "P1",
        "timestamps": {
            "created_at": now,
            "triaged_at": None,
            "assigned_at": None,
            "resolved_at": None,
            "closed_at": None,
            "updated_at": now
        },
        "location": {
            "type": "Point",
            "coordinates": [body.location.lng, body.location.lat]
        },
        "address_hint": body.address_hint,
        "zone_name": body.zone_name,
        "assignment": {"assigned_team_id": None},
        "evidence": [],
    }

    for attempt in range(12):
        seq = await _next_seq_for_year(year)
        request_id = _make_request_id(year, seq)

        doc = dict(doc_base)
        doc["request_id"] = request_id

        try:
            await service_requests_collection.insert_one(doc)

            actor = {
                "role": "citizen" if not body.citizen_ref.anonymous else "anonymous",
                "email": "citizen@system" if not body.citizen_ref.anonymous else "anonymous@system",
            }

            await audit_service.log_event({
                "time": datetime.utcnow(),
                "type": "request.create",
                "actor": actor,
                "entity": {"type": "service_request", "id": request_id},
                "message": f"Service request created: {request_id}",
                "meta": {
                    "anonymous": body.citizen_ref.anonymous,
                    "citizen_id": str(citizen_id) if citizen_id else None,
                    "contact_channel": body.citizen_ref.contact_channel,
                    "category": body.category,
                    "sub_category": body.sub_category,
                    "zone_name": body.zone_name,
                    "address_hint": body.address_hint,
                    "location": {"lng": body.location.lng, "lat": body.location.lat},
                    "status": "new",
                    "priority": "P1",
                }
            })

            return CreateServiceRequestResponse(
                request_id=request_id,
                status="new",
                sla_hint="Submitted. Waiting for triage."
            )

        except DuplicateKeyError:
            if attempt == 0:
                await _sync_counter_to_latest(year)
            continue

    raise HTTPException(500, "Failed to generate unique request_id after retries")


# =========================
# Evidence Upload
# =========================
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED = {"image/jpeg", "image/png", "image/jpg", "image/webp"}


@router.post("/{request_id}/evidence")
async def upload_evidence(
    request_id: str,
    request: Request,
    file: UploadFile = File(...),
    note: str | None = Form(default=None),
    x_citizen_id: str | None = Header(default=None, alias="X-Citizen-Id"),
    x_staff_id: str | None = Header(default=None, alias="X-Staff-Id"),
):
    doc = await service_requests_collection.find_one({"request_id": request_id})
    if not doc:
        raise HTTPException(404, "Request not found")

    if file.content_type not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    staff_oid = _parse_oid(x_staff_id)
    citizen_oid = _parse_oid(x_citizen_id)

    current_status = (doc.get("status") or "").strip().lower()

    # ✅ decide uploader + permissions
    if staff_oid:
        await _assert_staff_or_403(x_staff_id)

        # ✅ staff can upload ONLY when resolved
        if current_status != "resolved":
            raise HTTPException(400, "Staff can upload evidence ONLY when status=RESOLVED")

        uploader = "staff"
        uploader_id = staff_oid

    elif citizen_oid:
        _assert_owner_or_403(doc, citizen_oid)
        uploader = "citizen"
        uploader_id = citizen_oid

    else:
        raise HTTPException(403, "Missing X-Citizen-Id or X-Staff-Id")

    # ext
    ext = ".jpg"
    if file.content_type == "image/png":
        ext = ".png"
    elif file.content_type == "image/webp":
        ext = ".webp"

    safe_name = f"{request_id}-{uuid.uuid4().hex}{ext}"
    out_path = UPLOAD_DIR / safe_name
    out_path.write_bytes(await file.read())
    print("SAVED FILE:", out_path.resolve(), "SIZE:", out_path.stat().st_size)
    print("UPLOADER:", uploader, "STATUS:", current_status)

    public_base = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not public_base:
        raise HTTPException(500, "PUBLIC_BASE_URL is not set")

    file_url = f"{public_base}/uploads/{safe_name}"

    now = datetime.utcnow()
    evidence_item = {
        "type": "photo",
        "url": file_url,
        "uploaded_by": uploader,
        "uploaded_by_id": uploader_id,
        "uploaded_at": now,
    }
    if note:
        evidence_item["note"] = note

    await service_requests_collection.update_one(
        {"request_id": request_id},
        {"$push": {"evidence": evidence_item},
         "$set": {"timestamps.updated_at": now}}
    )

    return {"ok": True, "url": evidence_item["url"], "uploaded_by": uploader}


# =========================
# List Requests
# =========================
@router.get("")
async def list_service_requests(citizen_id: str | None = Query(default=None)):
    filt = {}

    if citizen_id:
        citizen_id = citizen_id.strip()
        if not ObjectId.is_valid(citizen_id):
            raise HTTPException(status_code=400, detail="Invalid citizen_id")
        filt["citizen_ref.citizen_id"] = ObjectId(citizen_id)

    rows = await service_requests_collection.find(filt) \
        .sort("timestamps.created_at", -1) \
        .to_list(length=200)

    out = []
    for d in rows:
        out.append({
            "request_id": d.get("request_id"),
            "status": d.get("status", ""),
            "description": d.get("description", ""),
            "category": d.get("category", ""),
            "sub_category": d.get("sub_category", ""),
            "created_at": (d.get("timestamps") or {}).get("created_at"),
        })
    return out


# =========================
# Update Request (ONLY NEW)
# =========================
@router.put("/{request_id}")
async def update_service_request(
    request_id: str,
    body: UpdateServiceRequestBody,
    x_citizen_id: str | None = Header(default=None, alias="X-Citizen-Id")
):
    citizen_oid = _parse_citizen_id(x_citizen_id)

    doc = await service_requests_collection.find_one({"request_id": request_id})
    if not doc:
        raise HTTPException(404, "Request not found")

    status = (doc.get("status") or "").lower()
    if status != "new":
        raise HTTPException(400, "Only NEW requests can be updated")

    _assert_owner_or_403(doc, citizen_oid)

    update_doc = {}
    if body.category is not None: update_doc["category"] = body.category
    if body.sub_category is not None: update_doc["sub_category"] = body.sub_category
    if body.description is not None: update_doc["description"] = body.description
    if body.tags is not None: update_doc["tags"] = body.tags
    if body.address_hint is not None: update_doc["address_hint"] = body.address_hint
    if body.zone_name is not None: update_doc["zone_name"] = body.zone_name

    if body.location is not None:
        update_doc["location"] = {
            "type": "Point",
            "coordinates": [body.location.lng, body.location.lat]
        }

    if not update_doc:
        raise HTTPException(400, "No fields to update")

    now = datetime.utcnow()
    update_doc["timestamps.updated_at"] = now

    changes = {}
    for k, v in update_doc.items():
        if k.startswith("timestamps."):
            continue
        before_val = doc.get(k)
        after_val = v
        if str(before_val) != str(after_val):
            changes[k] = {"from": before_val, "to": after_val}

    await service_requests_collection.update_one(
        {"request_id": request_id},
        {"$set": update_doc}
    )

    if changes:
        actor = _actor_from_request(doc, citizen_oid)
        await audit_service.log_event({
            "time": now,
            "type": "request.update",
            "actor": actor,
            "entity": {"type": "service_request", "id": request_id},
            "message": f"Service request updated: {request_id}",
            "meta": {"changes": changes}
        })

    return {"ok": True}


# =========================
# Delete Request (ONLY NEW)
# =========================
@router.delete("/{request_id}")
async def delete_service_request(
    request_id: str,
    x_citizen_id: str | None = Header(default=None, alias="X-Citizen-Id")
):
    citizen_oid = _parse_citizen_id(x_citizen_id)

    doc = await service_requests_collection.find_one({"request_id": request_id})
    if not doc:
        raise HTTPException(404, "Request not found")

    status = (doc.get("status") or "").lower()
    if status != "new":
        raise HTTPException(400, "Only NEW requests can be deleted")

    _assert_owner_or_403(doc, citizen_oid)

    now = datetime.utcnow()

    snapshot = {
        "category": doc.get("category"),
        "sub_category": doc.get("sub_category"),
        "zone_name": doc.get("zone_name"),
        "status": doc.get("status"),
        "priority": doc.get("priority"),
        "created_at": (doc.get("timestamps") or {}).get("created_at"),
    }

    res = await service_requests_collection.delete_one({"request_id": request_id})
    if res.deleted_count != 1:
        raise HTTPException(500, "Delete failed")

    actor = _actor_from_request(doc, citizen_oid)
    await audit_service.log_event({
        "time": now,
        "type": "request.delete",
        "actor": actor,
        "entity": {"type": "service_request", "id": request_id},
        "message": f"Service request deleted: {request_id}",
        "meta": {"snapshot": snapshot}
    })

    return {"ok": True}


# =========================
# Close Request (system/admin/employee action)
# =========================
@router.post("/{request_id}/close")
async def close_service_request(request_id: str):
    now = datetime.utcnow()

    doc = await service_requests_collection.find_one_and_update(
        {"request_id": request_id},
        {"$set": {
            "status": "closed",
            "timestamps.closed_at": now,
            "timestamps.updated_at": now
        }},
        return_document=ReturnDocument.AFTER
    )
    if not doc:
        raise HTTPException(404, "Request not found")

    await _upsert_perf_log(doc)

    await performance_logs_collection.update_one(
        {"request_id": doc["_id"]},
        {"$push": {"event_stream": {"type": "closed", "at": now}}},
        upsert=True
    )

    return {"ok": True}


# =========================
# Feedback (ONLY RESOLVED) -> close + perf log + audit
# =========================
@router.post("/{request_id}/feedback")
async def submit_feedback(
    request_id: str,
    body: CitizenFeedbackIn,
    x_citizen_id: str | None = Header(default=None, alias="X-Citizen-Id")
):
    citizen_oid = _parse_citizen_id(x_citizen_id)

    doc = await service_requests_collection.find_one({"request_id": request_id})
    if not doc:
        raise HTTPException(404, "Request not found")

    status = (doc.get("status") or "").lower()
    if status != "resolved":
        raise HTTPException(400, "Feedback is allowed only when status=RESOLVED")

    _assert_owner_or_403(doc, citizen_oid)

    now = datetime.utcnow()
    fb = {"stars": int(body.stars), "comment": body.comment, "submitted_at": now}

    # close request
    await service_requests_collection.update_one(
        {"request_id": request_id},
        {"$set": {
            "status": "closed",
            "timestamps.closed_at": now,
            "timestamps.updated_at": now
        }}
    )

    # ensure perf log exists + recompute KPIs
    await _ensure_performance_log_exists(doc)

    doc2 = await service_requests_collection.find_one({"request_id": request_id})
    await _upsert_perf_log(doc2)

    await performance_logs_collection.update_one(
        {"request_id": doc2["_id"]},
        {"$set": {"computed_kpis.citizen_feedback": fb},
         "$push": {"event_stream": {"type": "citizen_feedback", "at": now, "data": fb}}},
        upsert=True
    )

    # also push closed event (optional but keeps stream consistent)
    await performance_logs_collection.update_one(
        {"request_id": doc2["_id"]},
        {"$push": {"event_stream": {"type": "closed", "at": now}}},
        upsert=True
    )

    actor = _actor_from_request(doc, citizen_oid)
    await audit_service.log_event({
        "time": now,
        "type": "request.feedback",
        "actor": actor,
        "entity": {"type": "service_request", "id": request_id},
        "message": f"Citizen feedback submitted for request {request_id}",
        "meta": {"feedback": fb, "previous_status": "resolved", "new_status": "closed"}
    })

    return {"ok": True, "citizen_feedback": fb}


# =========================
# Staff: List My Teams
# =========================
@router.get("/staff/me/teams")
async def staff_my_teams(
    x_staff_id: str | None = Header(default=None, alias="X-Staff-Id")
):
    staff_oid = await _assert_staff_or_403(x_staff_id)

    teams = await team_collection.find({
        "deleted": False,
        "active": True,
        "members": str(staff_oid)
    }, {"name": 1, "shift": 1, "zones": 1, "skills": 1}).to_list(None)

    out = []
    for t in teams:
        out.append({
            "id": str(t["_id"]),
            "name": t.get("name"),
            "shift": t.get("shift"),
            "zones": t.get("zones", []),
            "skills": t.get("skills", []),
        })
    return out


# =========================
# Staff: List Tasks (All my teams)
# =========================
@router.get("/staff/tasks")
async def staff_list_tasks(
    x_staff_id: str | None = Header(default=None, alias="X-Staff-Id")
):
    staff_oid = await _assert_staff_or_403(x_staff_id)

    teams = await db["teams"].find({
        "deleted": {"$ne": True},
        "active": True,
        "members": str(staff_oid)
    }, {"_id": 1}).to_list(500)

    team_oids = [t["_id"] for t in teams]
    team_strs = [str(t["_id"]) for t in teams]

    if not team_oids and not team_strs:
        return []

    filt = {
        "$and": [
            {
                "$or": [
                    {"sla_policy.team_id": {"$in": team_oids}},
                    {"sla_policy.team_id": {"$in": team_strs}},
                ]
            },
            {
                "status": {"$nin": ["closed", "resolved"]}
            }
        ]
    }

    rows = await service_requests_collection.find(filt) \
        .sort("timestamps.created_at", -1) \
        .to_list(200)

    out = []
    for d in rows:
        coords = ((d.get("location") or {}).get("coordinates") or [None, None])
        lng, lat = coords[0], coords[1]
        out.append({
            "request_id": d.get("request_id"),
            "status": d.get("status", ""),
            "priority": d.get("priority", ""),
            "zone_name": d.get("zone_name", ""),
            "address_hint": d.get("address_hint", ""),
            "lat": lat,
            "lng": lng,
        })

    return out



# =========================
# Staff: Tasks By Selected Teams
# =========================
@router.get("/staff/tasks/by-teams")
async def staff_tasks_by_teams(
    team_ids: list[str] = Query(default=[]),
    x_staff_id: str | None = Header(default=None, alias="X-Staff-Id"),
):
    await _assert_staff_or_403(x_staff_id)

    team_oids = [ObjectId(t) for t in team_ids if ObjectId.is_valid(t)]
    team_strs = [t for t in team_ids if t]

    if not team_oids and not team_strs:
        return []

    filt = {
        "$or": [
            {"assignment.assigned_team_id": {"$in": team_oids}},
            {"sla_policy.team_id": {"$in": team_oids}},
            {"assignment.assigned_team_id": {"$in": team_strs}},
            {"sla_policy.team_id": {"$in": team_strs}},
        ]
    }

    rows = await service_requests_collection.find(filt).sort("timestamps.created_at", -1).to_list(200)

    out = []
    for d in rows:
        coords = ((d.get("location") or {}).get("coordinates") or [None, None])
        lng, lat = coords[0], coords[1]
        out.append({
            "request_id": d.get("request_id"),
            "status": d.get("status", ""),
            "priority": d.get("priority", ""),
            "zone_name": d.get("zone_name", ""),
            "address_hint": d.get("address_hint", ""),
            "lat": lat,
            "lng": lng,
        })
    return out


# =========================
# Staff: Update Status (no going back)
# =========================
@router.post("/staff/{request_id}/status")
async def staff_update_status(
    request_id: str,
    new_status: str = Form(...),
    x_staff_id: str | None = Header(default=None, alias="X-Staff-Id")
):
    await _assert_staff_or_403(x_staff_id)

    doc = await service_requests_collection.find_one({"request_id": request_id})
    if not doc:
        raise HTTPException(404, "Request not found")

    current = (doc.get("status") or "").strip().lower()
    ns = (new_status or "").strip().lower()

    # allowed statuses
    allowed = {"triaged", "assigned", "in_progress", "resolved"}
    if ns not in allowed:
        raise HTTPException(400, f"Invalid status. Allowed: {sorted(list(allowed))}")

    # forward-only transitions
    transitions = {
        "new": {"triaged"},
        "triaged": {"assigned"},
        "assigned": {"in_progress"},
        "in_progress": {"resolved"},
        "resolved": set(),
        "closed": set(),
    }

    if current not in transitions:
        raise HTTPException(400, f"Cannot change status from '{current}'")

    # prevent same status
    if ns == current:
        return {"ok": True, "status": current}

    # enforce forward-only
    if ns not in transitions[current]:
        raise HTTPException(
            400,
            f"Invalid transition: {current} -> {ns}. Allowed next: {sorted(list(transitions[current]))}"
        )

    now = datetime.utcnow()

    # ✅ SETS (timestamps)
    sets = {
        "status": ns,
        "timestamps.updated_at": now
    }
    if ns == "triaged":
        sets["timestamps.triaged_at"] = now
    if ns == "assigned":
        sets["timestamps.assigned_at"] = now
    if ns == "in_progress":
        sets["timestamps.in_progress_at"] = now  # ✅ ADDED
    if ns == "resolved":
        sets["timestamps.resolved_at"] = now

    await service_requests_collection.update_one(
        {"request_id": request_id},
        {"$set": sets}
    )

    # reload updated doc (so KPI computation uses latest status/timestamps)
    doc2 = await service_requests_collection.find_one({"request_id": request_id})

    # ✅ ensure perf log + update KPIs
    await _ensure_performance_log_exists(doc2)
    await _upsert_perf_log(doc2)

    # ✅ push event stream
    await performance_logs_collection.update_one(
        {"request_id": doc2["_id"]},
        {
            "$push": {
                "event_stream": {
                    "type": "status_changed",
                    "at": now,
                    "meta": {"from": current, "to": ns}
                }
            }
        },
        upsert=True
    )

    # ✅ AUDIT
    await audit_service.log_event(
        {
            "time": now,
            "type": "request.status_update",
            "actor": {"role": "staff", "id": x_staff_id},
            "entity": {"type": "request", "id": request_id},
            "message": f"Staff changed request status {current} → {ns}",
            "meta": {
                "from": current,
                "to": ns,
                "timestamps_set": [k for k in sets.keys() if k.startswith("timestamps.")],
            },
        }
    )

    return {"ok": True, "status": ns}



# =========================
# Staff: Close Direct (ONLY anonymous)
# =========================
@router.post("/staff/{request_id}/close")
async def staff_close_direct(
    request_id: str,
    x_staff_id: str | None = Header(default=None, alias="X-Staff-Id")
):
    await _assert_staff_or_403(x_staff_id)

    doc = await service_requests_collection.find_one({"request_id": request_id})
    if not doc:
        raise HTTPException(404, "Request not found")

    anonymous = (doc.get("citizen_ref") or {}).get("anonymous", False)
    if not anonymous:
        raise HTTPException(400, "Staff can close directly ONLY for anonymous requests.")

    status = (doc.get("status") or "").lower()
    if status == "closed":
        return {"ok": True, "status": "closed"}

    now = datetime.utcnow()
    await service_requests_collection.update_one(
        {"request_id": request_id},
        {"$set": {"status": "closed",
                  "timestamps.closed_at": now,
                  "timestamps.updated_at": now}}
    )

    await _ensure_performance_log_exists(doc)
    await performance_logs_collection.update_one(
        {"request_id": doc["_id"]},
        {"$push": {"event_stream": {"type": "closed_by_staff", "at": now}}},
        upsert=True
    )
    await performance_logs_collection.update_one(
        {"request_id": doc["_id"]},
        {"$push": {"event_stream": {"type": "closed", "at": now}}},
        upsert=True
    )

    # ✅ AUDIT
    await audit_service.log_event(
        {
            "time": now,
            "type": "request.close",
            "actor": {"role": "staff", "id": x_staff_id},
            "entity": {"type": "request", "id": request_id},
            "message": "Staff closed anonymous request directly",
            "meta": {"was_anonymous": True},
        }
    )



    return {"ok": True, "status": "closed"}

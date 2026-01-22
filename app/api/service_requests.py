# app/api/service_requests.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Header
from datetime import datetime
from bson import ObjectId
from pathlib import Path
import uuid

from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

from app.db.mongo import service_requests_collection, db
from app.schemas.service_request import (
    CreateServiceRequestBody,
    CreateServiceRequestResponse,
    UpdateServiceRequestBody,
    CitizenFeedbackIn,
)

router = APIRouter(prefix="/service-requests", tags=["Service Requests"])

performance_logs_collection = db["performance_logs"]
counters_collection = db["counters"]


# -------------------------
# Helpers
# -------------------------
def _make_request_id(year: int, seq: int) -> str:
    return f"CST-{year}-{seq:04d}"


def _parse_citizen_id(x_citizen_id: str | None) -> ObjectId | None:
    if not x_citizen_id:
        return None
    x_citizen_id = x_citizen_id.strip()
    if not ObjectId.is_valid(x_citizen_id):
        return None
    return ObjectId(x_citizen_id)


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

    # base doc (without request_id)
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

    # ✅ retry loop with self-healing counter
    for attempt in range(12):
        seq = await _next_seq_for_year(year)
        request_id = _make_request_id(year, seq)

        doc = dict(doc_base)
        doc["request_id"] = request_id

        try:
            await service_requests_collection.insert_one(doc)

            return CreateServiceRequestResponse(
                request_id=request_id,
                status="new",
                sla_hint="Submitted. Waiting for triage."
            )

        except DuplicateKeyError:
            # If counter is behind, sync once then keep retrying
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
    file: UploadFile = File(...),
    note: str | None = Form(default=None)
):
    doc = await service_requests_collection.find_one({"request_id": request_id})
    if not doc:
        raise HTTPException(404, "Request not found")

    if file.content_type not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    ext = ".jpg"
    if file.content_type == "image/png":
        ext = ".png"
    elif file.content_type == "image/webp":
        ext = ".webp"

    safe_name = f"{request_id}-{uuid.uuid4().hex}{ext}"
    out_path = UPLOAD_DIR / safe_name

    contents = await file.read()
    out_path.write_bytes(contents)

    now = datetime.utcnow()
    evidence_item = {
        "type": "photo",
        "url": f"/uploads/{safe_name}",
        "uploaded_by": "citizen",
        "uploaded_at": now
    }
    if note:
        evidence_item["note"] = note

    await service_requests_collection.update_one(
        {"request_id": request_id},
        {"$push": {"evidence": evidence_item},
         "$set": {"timestamps.updated_at": now}}
    )

    return {"ok": True, "url": evidence_item["url"]}


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

    update_doc["timestamps.updated_at"] = datetime.utcnow()

    await service_requests_collection.update_one(
        {"request_id": request_id},
        {"$set": update_doc}
    )
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

    await service_requests_collection.delete_one({"request_id": request_id})
    return {"ok": True}


# =========================
# Close Request (system/admin/employee action)
# =========================
@router.post("/{request_id}/close")
async def close_service_request(request_id: str):
    doc = await service_requests_collection.find_one({"request_id": request_id})
    if not doc:
        raise HTTPException(404, "Request not found")

    now = datetime.utcnow()

    await service_requests_collection.update_one(
        {"request_id": request_id},
        {"$set": {
            "status": "closed",
            "timestamps.closed_at": now,
            "timestamps.updated_at": now
        }}
    )

    await _ensure_performance_log_exists(doc)

    await performance_logs_collection.update_one(
        {"request_id": doc["_id"]},
        {"$push": {"event_stream": {"type": "closed", "at": now}}},
        upsert=True
    )

    return {"ok": True}


# =========================
# Feedback (ONLY RESOLVED) -> then CLOSE + create log if missing
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
    fb = {
        "stars": int(body.stars),
        "comment": body.comment,
        "submitted_at": now
    }

    await service_requests_collection.update_one(
        {"request_id": request_id},
        {"$set": {
            "status": "closed",
            "timestamps.closed_at": now,
            "timestamps.updated_at": now
        }}
    )

    await _ensure_performance_log_exists(doc)

    await performance_logs_collection.update_one(
        {"request_id": doc["_id"]},
        {"$set": {"computed_kpis.citizen_feedback": fb},
         "$push": {"event_stream": {"type": "citizen_feedback", "at": now, "data": fb}}},
        upsert=True
    )

    await performance_logs_collection.update_one(
        {"request_id": doc["_id"]},
        {"$push": {"event_stream": {"type": "closed", "at": now}}},
        upsert=True
    )

    return {"ok": True, "citizen_feedback": fb}

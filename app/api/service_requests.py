from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from datetime import datetime
from bson import ObjectId
from pathlib import Path
import uuid

from app.db.mongo import service_requests_collection
from app.schemas.service_request import CreateServiceRequestBody, CreateServiceRequestResponse

router = APIRouter(prefix="/service-requests", tags=["Service Requests"])

def _next_request_id(now: datetime, seq: int) -> str:
    return f"CST-{now.year}-{seq:04d}"


@router.post("", response_model=CreateServiceRequestResponse)
async def create_service_request(body: CreateServiceRequestBody):
    now = datetime.utcnow()

    count = await service_requests_collection.count_documents({})
    request_id = _next_request_id(now, count + 1)

    citizen_id = None
    if body.citizen_ref.citizen_id:
        try:
            citizen_id = ObjectId(body.citizen_ref.citizen_id)
        except:
            raise HTTPException(400, "Invalid citizen_id")

    doc = {
        "request_id": request_id,
        "citizen_ref": {
            "citizen_id": citizen_id,
            "anonymous": body.citizen_ref.anonymous,
            "contact_channel": body.citizen_ref.contact_channel
        },
        "category": body.category,
        "sub_category": body.sub_category,
        "description": body.description,
        "tags": body.tags,
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
            "coordinates": [body.location.lng, body.location.lat]  # [lng,lat]
        },
        "address_hint": body.address_hint,
        "zone_name": body.zone_name,
        "assignment": {"team_id": None},
        "evidence": []
    }

    await service_requests_collection.insert_one(doc)

    return CreateServiceRequestResponse(
        request_id=request_id,
        status="new",
        sla_hint="Submitted. Waiting for triage."
    )


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
        {
            "$push": {"evidence": evidence_item},
            "$set": {"timestamps.updated_at": now}
        }
    )

    return {"ok": True, "url": evidence_item["url"]}

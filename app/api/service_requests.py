# from fastapi import APIRouter, HTTPException, UploadFile, File, Form,Query
# from datetime import datetime
# from bson import ObjectId
# from pathlib import Path
# import uuid
#
# from app.db.mongo import service_requests_collection
# from app.schemas.service_request import CreateServiceRequestBody, CreateServiceRequestResponse
#
# router = APIRouter(prefix="/service-requests", tags=["Service Requests"])
#
# from pymongo.errors import DuplicateKeyError
# import re
#
# def _parse_seq(request_id: str) -> int:
#     # CST-2026-0004 → 4
#     return int(request_id.split("-")[-1])
#
# def _make_request_id(year: int, seq: int) -> str:
#     return f"CST-{year}-{seq:04d}"
#
#
#
# @router.post("", response_model=CreateServiceRequestResponse)
# async def create_service_request(body: CreateServiceRequestBody):
#
#     now = datetime.utcnow()
#     year = now.year
#
#     # ✅ citizen_id: store ONLY if not anonymous
#     citizen_id = None
#     if not body.citizen_ref.anonymous:
#         if body.citizen_ref.citizen_id:
#             try:
#                 citizen_id = ObjectId(body.citizen_ref.citizen_id)
#             except:
#                 raise HTTPException(400, "Invalid citizen_id")
#         else:
#             raise HTTPException(400, "citizen_id is required when anonymous=false")
#
#     # 🔁 retry loop (safe)
#     for _ in range(5):
#
#         # 1️⃣ get last request of this year
#         last = await service_requests_collection.find_one(
#             {"request_id": {"$regex": f"^CST-{year}-"}},
#             sort=[("request_id", -1)]
#         )
#
#         next_seq = (_parse_seq(last["request_id"]) + 1) if last else 1
#         request_id = _make_request_id(year, next_seq)
#
#         doc = {
#             "request_id": request_id,
#             "citizen_ref": {
#                 "citizen_id": citizen_id,  # ✅ null if anonymous
#                 "anonymous": body.citizen_ref.anonymous,
#                 "contact_channel": body.citizen_ref.contact_channel
#             },
#             "category": body.category,
#             "sub_category": body.sub_category,
#             "description": body.description,
#             "tags": body.tags or [],
#             "status": "new",
#             "priority": "P1",
#             "timestamps": {
#                 "created_at": now,
#                 "triaged_at": None,
#                 "assigned_at": None,
#                 "resolved_at": None,
#                 "closed_at": None,
#                 "updated_at": now
#             },
#             "location": {
#                 "type": "Point",
#                 "coordinates": [body.location.lng, body.location.lat]
#             },
#             "address_hint": body.address_hint,
#             "zone_name": body.zone_name,
#             "assignment": {"assigned_team_id": None},
#             "evidence": []
#         }
#
#         try:
# <<<<<<< HEAD
#             citizen_id = ObjectId(body.citizen_ref.citizen_id)
#         except:
#             raise HTTPException(400, "Invalid citizen_id")
#
#     doc = {
#         "request_id": request_id,
#         "citizen_ref": {
#             "citizen_id": citizen_id,
#             "anonymous": body.citizen_ref.anonymous,
#             "contact_channel": body.citizen_ref.contact_channel
#         },
#         "category": body.category,
#         "sub_category": body.sub_category,
#         "description": body.description,
#         "tags": body.tags,
#         "status": "new",
#         "priority": "P1",
#         "timestamps": {
#             "created_at": now,
#             "triaged_at": None,
#             "assigned_at": None,
#             "resolved_at": None,
#             "closed_at": None,
#             "updated_at": now
#         },
#         "location": {
#             "type": "Point",
#             "coordinates": [body.location.lng, body.location.lat]  # [lng,lat]
#         },
#         "address_hint": body.address_hint,
#         "zone_name": body.zone_name,
#         "assignment": {"team_id": None},
#         "evidence": []
#     }
#
#     await service_requests_collection.insert_one(doc)
#
#     return CreateServiceRequestResponse(
#         request_id=request_id,
#         status="new",
#         sla_hint="Submitted. Waiting for triage."
#     )
# =======
#             await service_requests_collection.insert_one(doc)
#             return CreateServiceRequestResponse(
#                 request_id=request_id,
#                 status="new",
#                 sla_hint="Submitted. Waiting for triage."
#             )
#         except DuplicateKeyError:
#             continue
# >>>>>>> 71dc3dd4951c222c41ab6f857a6ef756a9615704
#
#     raise HTTPException(500, "Failed to generate unique request id")
#
# # =========================
# # Evidence Upload
# # =========================
# UPLOAD_DIR = Path("uploads")
# UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
#
# ALLOWED = {"image/jpeg", "image/png", "image/jpg", "image/webp"}
#
# @router.post("/{request_id}/evidence")
# async def upload_evidence(
#     request_id: str,
#     file: UploadFile = File(...),
#     note: str | None = Form(default=None)
# ):
#     doc = await service_requests_collection.find_one({"request_id": request_id})
#     if not doc:
#         raise HTTPException(404, "Request not found")
#
#     if file.content_type not in ALLOWED:
#         raise HTTPException(400, f"Unsupported file type: {file.content_type}")
#
#     ext = ".jpg"
#     if file.content_type == "image/png":
#         ext = ".png"
#     elif file.content_type == "image/webp":
#         ext = ".webp"
#
#     safe_name = f"{request_id}-{uuid.uuid4().hex}{ext}"
#     out_path = UPLOAD_DIR / safe_name
#
#     contents = await file.read()
#     out_path.write_bytes(contents)
#
#     now = datetime.utcnow()
#     evidence_item = {
#         "type": "photo",
#         "url": f"/uploads/{safe_name}",
#         "uploaded_by": "citizen",
#         "uploaded_at": now
#     }
#     if note:
#         evidence_item["note"] = note
#
#     await service_requests_collection.update_one(
#         {"request_id": request_id},
#         {
#             "$push": {"evidence": evidence_item},
#             "$set": {"timestamps.updated_at": now}
#         }
#     )
#
#     return {"ok": True, "url": evidence_item["url"]}
#
# @router.get("")
# async def list_service_requests(citizen_id: str | None = Query(default=None)):
#     filt = {}
#
#     if citizen_id:
#         citizen_id = citizen_id.strip()
#
#         # prevent crashes
#         if not ObjectId.is_valid(citizen_id):
#             raise HTTPException(status_code=400, detail="Invalid citizen_id")
#
#         filt["citizen_ref.citizen_id"] = ObjectId(citizen_id)
#
#     rows = await service_requests_collection.find(filt)\
#         .sort("timestamps.created_at", -1)\
#         .to_list(length=200)
#
#     out = []
#     for d in rows:
#         out.append({
#             "request_id": d.get("request_id"),
#             "status": d.get("status", ""),
#             "description": d.get("description", ""),
#             "category": d.get("category", ""),
#             "sub_category": d.get("sub_category", ""),
#             "created_at": (d.get("timestamps") or {}).get("created_at")
#         })
#     return out
#
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from datetime import datetime
from bson import ObjectId
from pathlib import Path
import uuid

from pymongo.errors import DuplicateKeyError

from app.db.mongo import service_requests_collection
from app.schemas.service_request import CreateServiceRequestBody, CreateServiceRequestResponse

router = APIRouter(prefix="/service-requests", tags=["Service Requests"])


def _parse_seq(request_id: str) -> int:
    # CST-2026-0004 → 4
    return int(request_id.split("-")[-1])


def _make_request_id(year: int, seq: int) -> str:
    return f"CST-{year}-{seq:04d}"


@router.post("", response_model=CreateServiceRequestResponse)
async def create_service_request(body: CreateServiceRequestBody):
    now = datetime.utcnow()
    year = now.year

    # ✅ citizen_id: store ONLY if not anonymous
    citizen_id = None
    if not body.citizen_ref.anonymous:
        if body.citizen_ref.citizen_id:
            if not ObjectId.is_valid(body.citizen_ref.citizen_id):
                raise HTTPException(400, "Invalid citizen_id")
            citizen_id = ObjectId(body.citizen_ref.citizen_id)
        else:
            raise HTTPException(400, "citizen_id is required when anonymous=false")

    # 🔁 retry loop (safe)
    for _ in range(5):
        # 1️⃣ get last request of this year
        last = await service_requests_collection.find_one(
            {"request_id": {"$regex": f"^CST-{year}-"}},
            sort=[("request_id", -1)]
        )

        next_seq = (_parse_seq(last["request_id"]) + 1) if last else 1
        request_id = _make_request_id(year, next_seq)

        doc = {
            "request_id": request_id,
            "citizen_ref": {
                "citizen_id": citizen_id,  # ✅ null if anonymous
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
                "coordinates": [body.location.lng, body.location.lat]  # [lng, lat]
            },
            "address_hint": body.address_hint,
            "zone_name": body.zone_name,
            "assignment": {"assigned_team_id": None},
            "evidence": []
        }

        try:
            await service_requests_collection.insert_one(doc)
            return CreateServiceRequestResponse(
                request_id=request_id,
                status="new",
                sla_hint="Submitted. Waiting for triage."
            )
        except DuplicateKeyError:
            # rare race condition → retry
            continue

    raise HTTPException(500, "Failed to generate unique request id")


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
            "created_at": (d.get("timestamps") or {}).get("created_at")
        })

    return out
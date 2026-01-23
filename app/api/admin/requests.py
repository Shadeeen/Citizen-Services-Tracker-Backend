from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from app.db.mongo import requests_collection, users_collection, performance_logs_collection
from app.utils.mongo import serialize_mongo

router = APIRouter(prefix="/admin/requests", tags=["Admin Requests"])


def _split_evidence(doc: dict):
    evidence = doc.get("evidence")

    if isinstance(evidence, dict):
        citizen = evidence.get("citizen") if isinstance(evidence.get("citizen"), list) else []
        employee = evidence.get("employee") if isinstance(evidence.get("employee"), list) else []
        return citizen, employee

    if isinstance(evidence, list):
        citizen = [x for x in evidence if str(x.get("uploaded_by", "")).lower() == "citizen"]
        employee = [
            x for x in evidence
            if str(x.get("uploaded_by", "")).lower() in {"employee", "staff", "admin", "municipality"}
        ]
        return citizen, employee

    return [], []


async def _attach_citizen(doc: dict):
    citizen_data = None
    citizen_ref = doc.get("citizen_ref")

    if citizen_ref and not citizen_ref.get("anonymous"):
        citizen_id = citizen_ref.get("citizen_id")

        cit_oid = None
        if isinstance(citizen_id, ObjectId):
            cit_oid = citizen_id
        elif citizen_id and ObjectId.is_valid(str(citizen_id)):
            cit_oid = ObjectId(str(citizen_id))

        if cit_oid:
            user = await users_collection.find_one({"_id": cit_oid, "role": "citizen"})
            if user:
                user = serialize_mongo(user)
                citizen_data = {
                    "full_name": user.get("full_name"),
                    "phone": user.get("contacts", {}).get("phone"),
                    "email": user.get("contacts", {}).get("email"),
                }

    doc["citizen"] = citizen_data
    return doc


# ✅ LIST ALL REQUESTS
@router.get("/")
async def list_requests():
    cursor = requests_collection.find().sort("timestamps.created_at", -1)

    results = []
    async for doc in cursor:
        doc = serialize_mongo(doc)
        doc["id"] = doc.pop("_id")
        results.append(doc)

    return results


# ✅ FEEDBACK LIST (put before /{request_id})
@router.get("/feedbacks")
async def list_feedback_requests(
    status: str = Query("resolved", regex="^(resolved|closed)$"),
    limit: int = Query(200, ge=1, le=500),
):
    st = status.lower()

    pipeline = [
        {"$match": {"status": st}},
        {"$sort": {"timestamps.created_at": -1}},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "performance_logs",
                "localField": "_id",
                "foreignField": "request_id",
                "as": "perf",
            }
        },
        {"$unwind": {"path": "$perf", "preserveNullAndEmptyArrays": True}},
        {
            "$addFields": {
                "citizen_feedback": "$perf.computed_kpis.citizen_feedback",
                "performance_log_id": "$perf._id",
            }
        },
        {"$project": {"perf": 0}},
    ]

    cursor = requests_collection.aggregate(pipeline)

    out = []
    async for doc in cursor:
        doc = serialize_mongo(doc)
        doc["id"] = doc.pop("_id")

        citizen_ev, employee_ev = _split_evidence(doc)
        doc["citizen_evidence"] = citizen_ev
        doc["employee_evidence"] = employee_ev

        doc = await _attach_citizen(doc)
        out.append(doc)

    return out


@router.get("/{request_id}/feedback-details")
async def get_request_feedback_details(request_id: str):
    doc = await requests_collection.find_one({"request_id": request_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Request not found")

    perf = await performance_logs_collection.find_one({"request_id": doc["_id"]})

    doc = serialize_mongo(doc)
    doc["id"] = doc.pop("_id")
    doc = await _attach_citizen(doc)

    citizen_ev, employee_ev = _split_evidence(doc)
    doc["citizen_evidence"] = citizen_ev
    doc["employee_evidence"] = employee_ev

    if perf:
        perf = serialize_mongo(perf)
        doc["citizen_feedback"] = (perf.get("computed_kpis") or {}).get("citizen_feedback")
        doc["performance_log"] = {
            "id": perf.get("_id"),
            "computed_kpis": perf.get("computed_kpis"),
            "event_stream": perf.get("event_stream", []),
        }
    else:
        doc["citizen_feedback"] = None
        doc["performance_log"] = None

    return doc


# ✅ GET SINGLE REQUEST (WITH CITIZEN DATA) — safe now
@router.get("/{request_id}")
async def get_request(request_id: str):
    doc = await requests_collection.find_one({"request_id": request_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Request not found")

    doc = serialize_mongo(doc)
    doc["id"] = doc.pop("_id")
    doc = await _attach_citizen(doc)
    return doc

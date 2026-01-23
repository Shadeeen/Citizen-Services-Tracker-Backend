from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone

from app.db.mongo import requests_collection, users_collection, performance_logs_collection
from app.utils.mongo import serialize_mongo

router = APIRouter(prefix="/admin/requests", tags=["Admin Requests"])


def _to_dt(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        s = str(v)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except:
        return None


def _compute_state(elapsed_min, target_hours, breach_hours):
    if elapsed_min is None or target_hours is None:
        return None

    target_min = int(float(target_hours) * 60)
    breach_min = int(float(breach_hours) * 60) if breach_hours is not None else None

    if breach_min is not None and elapsed_min >= breach_min:
        return "breached"
    if elapsed_min >= target_min:
        return "at_risk"
    return "on_track"
@router.get("/{request_id}/sla-monitoring")
async def get_sla_monitoring(request_id: str):
    req = await requests_collection.find_one({"request_id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    # find perf by multiple possible keys (ObjectId or string)
    perf = await performance_logs_collection.find_one({
        "$or": [
            {"request_id": req["_id"]},
            {"request_id": request_id},
            {"request_id": str(req["_id"])},
        ]
    })

    # compute elapsed from request created_at
    created_at = (req.get("timestamps") or {}).get("created_at") or req.get("created_at")
    created_dt = _to_dt(created_at)
    now = datetime.now(timezone.utc)
    elapsed_min = int((now - created_dt).total_seconds() // 60) if created_dt else None

    sla = req.get("sla_policy") or {}

    # ✅ ALWAYS define kpis so you can safely use it later
    kpis = {}

    if perf:
        perf_ser = serialize_mongo(perf)
        kpis = perf_ser.get("computed_kpis") or {}

    # target/breach fallback: KPIs -> request.sla_policy
    target_hours = kpis.get("sla_target_hours") or sla.get("target_hours")
    breach_hours = kpis.get("breach_threshold_hours") or sla.get("breach_threshold_hours")

    state = kpis.get("sla_state") or _compute_state(elapsed_min, target_hours, breach_hours)

    target_min = int(float(target_hours) * 60) if target_hours is not None else None
    breach_min = int(float(breach_hours) * 60) if breach_hours is not None else None

    rem_target = max(target_min - elapsed_min, 0) if (elapsed_min is not None and target_min is not None) else None
    rem_breach = max(breach_min - elapsed_min, 0) if (elapsed_min is not None and breach_min is not None) else None

    return {
        "request_id": request_id,
        "request_db_id": str(req["_id"]),
        "monitoring": {
            "state": state,
            "elapsed_minutes": elapsed_min,
            "sla_target_hours": target_hours,
            "breach_threshold_hours": breach_hours,
            "remaining_to_target_minutes": rem_target,
            "remaining_to_breach_minutes": rem_breach,
            "escalation_count": kpis.get("escalation_count"),
            "breach_reason": kpis.get("breach_reason"),
            "resolution_minutes": kpis.get("resolution_minutes"),
        },
        "performance_log": None if not perf else {
            "id": str(perf_ser.get("_id")),
            "event_stream": perf_ser.get("event_stream", []),
        },
        "computed_kpis": None if not perf else kpis,
    }



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

from fastapi import Query
from bson import ObjectId

@router.get("/assigned/by-team")
async def list_assigned_requests_for_team(
    team_id: str = Query(..., min_length=1),
    status: str = Query("assigned"),  # default only assigned
    limit: int = Query(200, ge=1, le=500),
):
    """
    Returns requests assigned to a specific team.
    Matches both:
      - assignment.assigned_team_id (string)
      - sla_policy.team_id (ObjectId)
    """

    team_id = team_id.strip()
    team_oid = ObjectId(team_id) if ObjectId.is_valid(team_id) else None

    ors = [{"assignment.assigned_team_id": team_id}]
    if team_oid:
        ors.append({"sla_policy.team_id": team_oid})

    match = {"$or": ors}

    # optional status filter:
    if status and status != "all":
        match["status"] = status

    pipeline = [
        {"$match": match},
        {"$sort": {"timestamps.created_at": -1}},
        {"$limit": limit},
    ]

    cursor = requests_collection.aggregate(pipeline)

    out = []
    async for doc in cursor:
        doc = serialize_mongo(doc)
        doc["id"] = doc.pop("_id")
        doc = await _attach_citizen(doc)

        citizen_ev, employee_ev = _split_evidence(doc)
        doc["citizen_evidence"] = citizen_ev
        doc["employee_evidence"] = employee_ev

        out.append(doc)

    return out

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

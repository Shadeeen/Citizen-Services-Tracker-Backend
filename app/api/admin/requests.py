from bson import ObjectId
from fastapi import APIRouter, HTTPException

from app.db.mongo import requests_collection, users_collection
from app.utils.mongo import serialize_mongo
router = APIRouter(prefix="/admin/requests", tags=["Admin Requests"])


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


# ✅ GET SINGLE REQUEST (WITH CITIZEN DATA)
@router.get("/{request_id}")
async def get_request(request_id: str):
    doc = await requests_collection.find_one({"request_id": request_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Request not found")

    citizen_data = None
    citizen_ref = doc.get("citizen_ref")

    if citizen_ref and not citizen_ref.get("anonymous"):
        citizen_id = citizen_ref.get("citizen_id")

        if citizen_id:
            user = await users_collection.find_one({
                "_id": ObjectId(citizen_id),
                "role": "citizen"
            })

            if user:
                user = serialize_mongo(user)
                citizen_data = {
                    "full_name": user.get("full_name"),
                    "phone": user.get("contacts", {}).get("phone"),
                    "email": user.get("contacts", {}).get("email"),
                }

    doc = serialize_mongo(doc)
    doc["id"] = doc.pop("_id")
    doc["citizen"] = citizen_data

    return doc


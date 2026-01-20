from fastapi import APIRouter, HTTPException
from app.db.mongo import requests_collection
from app.utils.mongo import serialize_mongo

router = APIRouter(prefix="/admin/requests", tags=["Admin Requests"])


@router.get("")
async def list_requests():
    cursor = requests_collection.find().sort("timestamps.created_at", -1)

    results = []
    async for doc in cursor:
        doc = serialize_mongo(doc)
        doc["id"] = doc.pop("_id")   # rename _id → id
        results.append(doc)

    return results


@router.get("/{request_id}")
async def get_request(request_id: str):
    doc = await requests_collection.find_one({"request_id": request_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Request not found")

    doc = serialize_mongo(doc)
    doc["id"] = doc.pop("_id")
    return doc

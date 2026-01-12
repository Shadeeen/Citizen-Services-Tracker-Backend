from app.db.mongo import sla_collection
from app.models.sla_policy import build_sla_doc

async def list_policies():
    out = []
    async for doc in sla_collection.find():
        doc["id"] = doc.pop("_id")
        out.append(doc)
    return out

async def create_policy(data):
    doc = build_sla_doc(data.dict())
    await sla_collection.insert_one(doc)
    doc["id"] = doc.pop("_id")
    return doc

async def update_policy(policy_id: str, patch: dict):
    await sla_collection.update_one(
        {"_id": policy_id},
        {"$set": patch},
    )
    doc = await sla_collection.find_one({"_id": policy_id})
    if not doc:
        return None
    doc["id"] = doc.pop("_id")
    return doc

async def toggle_active(policy_id: str):
    doc = await sla_collection.find_one({"_id": policy_id})
    if not doc:
        return None

    new_state = not doc.get("active", True)
    await sla_collection.update_one(
        {"_id": policy_id},
        {"$set": {"active": new_state}},
    )

    doc["active"] = new_state
    doc["id"] = doc.pop("_id")
    return doc

async def delete_policy(policy_id: str):
    res = await sla_collection.delete_one({"_id": policy_id})
    return res.deleted_count == 1

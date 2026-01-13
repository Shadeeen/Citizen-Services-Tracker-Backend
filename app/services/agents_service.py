from bson import ObjectId
from app.db.mongo import db as mongo_db

COL = "service_agents"

def _out(doc):
    return {
        "id": str(doc["_id"]),
        "full_name": doc["full_name"],
        "email": doc["email"],
        "phone": doc.get("phone"),
        "team_id": doc.get("team_id"),
        "zones": doc.get("zones", []),
        "skills": doc.get("skills", []),
        "shift": doc.get("shift", "Day"),
        "workload_open": doc.get("workload_open", 0),
        "active": doc.get("active", True),
    }

async def list_agents():
    db = mongo_db
    cur = db[COL].find({}).sort("_id", -1)
    return [_out(x) async for x in cur]

async def create_agent(data):
    db = mongo_db
    doc = data.dict()
    doc["email"] = doc["email"].lower().strip()
    doc["active"] = True

    exists = await db[COL].count_documents({"email": doc["email"]})
    if exists:
        raise ValueError("Email already exists")

    res = await db[COL].insert_one(doc)
    saved = await db[COL].find_one({"_id": res.inserted_id})
    return _out(saved)

async def update_agent(agent_id: str, patch: dict):
    db = mongo_db
    try:
        oid = ObjectId(agent_id)
    except:
        return None

    if "email" in patch and patch["email"] is not None:
        patch["email"] = patch["email"].lower().strip()
        exists = await db[COL].count_documents({"email": patch["email"], "_id": {"$ne": oid}})
        if exists:
            raise ValueError("Email already exists")

    await db[COL].update_one({"_id": oid}, {"$set": patch})
    doc = await db[COL].find_one({"_id": oid})
    return _out(doc) if doc else None

async def toggle_agent_active(agent_id: str):
    db = mongo_db
    try:
        oid = ObjectId(agent_id)
    except:
        return None

    agent = await db[COL].find_one({"_id": oid})
    if not agent:
        return None

    new_active = not agent.get("active", True)
    await db[COL].update_one({"_id": oid}, {"$set": {"active": new_active}})
    doc = await db[COL].find_one({"_id": oid})
    return _out(doc)

async def delete_agent(agent_id: str):
    db = mongo_db
    try:
        oid = ObjectId(agent_id)
    except:
        return False
    res = await db[COL].delete_one({"_id": oid})
    return res.deleted_count == 1

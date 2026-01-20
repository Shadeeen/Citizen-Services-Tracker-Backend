from datetime import datetime
from bson import ObjectId
from app.db.mongo import users_collection
from app.core.security import hash_password, verify_password


def _to_out(doc):
    return {
        "id": str(doc["_id"]),
        "full_name": doc.get("full_name"),
        "email": doc.get("email") or doc.get("contacts", {}).get("email"),
        "role": doc.get("role"),
        "is_active": doc.get("is_active", True),
        "type": "admin" if doc.get("role") else "citizen",
        "created_at": doc.get("created_at"),
    }


async def list_users(q: str | None = None, role: str | None = None, active: bool | None = None):
    filt = {"deleted": {"$ne": True}}

    if role:
        filt["role"] = role

    if active is not None:
        filt["is_active"] = active

    if q:
        filt["$or"] = [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"contacts.email": {"$regex": q, "$options": "i"}},
        ]

    rows = await users_collection.find(filt).sort("created_at", -1).to_list(length=200)
    return [_to_out(d) for d in rows]


async def create_user(data):
    existing = await users_collection.find_one({
        "email": data.email,
        "deleted": {"$ne": True}
    })
    if existing:
        return None

    doc = {
        "full_name": data.full_name,
        "email": data.email,
        "password_hash": hash_password(data.password),
        "role": data.role.value,
        "is_active": data.is_active,
        "created_at": datetime.utcnow(),
        "deleted": False,
    }

    res = await users_collection.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _to_out(doc)


async def get_user(user_id: str):
    doc = await users_collection.find_one({
        "_id": ObjectId(user_id),
        "deleted": {"$ne": True}
    })
    return _to_out(doc) if doc else None


async def update_user(user_id: str, patch: dict):
    doc = await users_collection.find_one({
        "_id": ObjectId(user_id),
        "deleted": {"$ne": True}
    })
    if not doc:
        return None

    update_doc = {}
    if "full_name" in patch:
        update_doc["full_name"] = patch["full_name"]
    if "role" in patch:
        update_doc["role"] = patch["role"]
    if "is_active" in patch:
        update_doc["is_active"] = patch["is_active"]
    if "password" in patch:
        update_doc["password_hash"] = hash_password(patch["password"])

    if update_doc:
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_doc}
        )

    doc2 = await users_collection.find_one({"_id": ObjectId(user_id)})
    return _to_out(doc2)


async def toggle_user_active(user_id: str):
    doc = await users_collection.find_one({
        "_id": ObjectId(user_id),
        "deleted": {"$ne": True}
    })
    if not doc:
        return None

    new_active = not doc.get("is_active", True)
    await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"is_active": new_active}}
    )

    doc2 = await users_collection.find_one({"_id": ObjectId(user_id)})
    return _to_out(doc2)


async def delete_user(user_id: str):
    res = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"deleted": True}}
    )
    return res.modified_count == 1


async def get_user_by_email(email: str):
    doc = await users_collection.find_one({
        "email": email,
        "deleted": {"$ne": True}
    })
    return _to_out(doc) if doc else None


async def login(email: str, password: str):
    doc = await users_collection.find_one({
        "email": email,
        "deleted": {"$ne": True}
    })

    if not doc:
        return None

    if not doc.get("is_active", True):
        return "inactive"

    if not verify_password(password, doc["password_hash"]):
        return None

    return _to_out(doc)

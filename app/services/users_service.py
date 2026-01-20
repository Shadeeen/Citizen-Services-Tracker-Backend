from __future__ import annotations

from datetime import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.db.mongo import users_collection
from app.core.security import hash_password, verify_password
from app.mapper.users_mapper import to_user_out


# -------------------------
# Helpers
# -------------------------
def _email_norm(email: str) -> str:
    return (email or "").lower().strip()


def _phone_norm(phone: str | None) -> str | None:
    if not phone:
        return None
    p = phone.strip()
    return p if p else None


# -------------------------
# Users CRUD
# -------------------------
async def list_users(q: str | None = None, role: str | None = None, active: bool | None = None):
    filt: dict = {"deleted": {"$ne": True}}

    if role:
        filt["role"] = role

    if active is not None:
        filt["is_active"] = active

    if q:
        filt["$or"] = [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"contacts.email": {"$regex": q, "$options": "i"}},
            {"contacts.phone": {"$regex": q, "$options": "i"}},
        ]

    rows = await users_collection.find(filt).sort("created_at", -1).to_list(length=200)
    return [to_user_out(d) for d in rows]


async def create_user(users_col, body):
    """
    Create user with NEW structure:
    - contacts.email / contacts.phone
    - verification, preferences ...
    """
    now = datetime.utcnow()

    email_norm = _email_norm(body.email)
    phone_norm = _phone_norm(getattr(body, "phone", None))

    # prevent duplicates (works even without unique index)
    existing = await users_col.find_one({"contacts.email": email_norm, "deleted": {"$ne": True}})
    if existing:
        return None

    doc = {
        "full_name": getattr(body, "full_name", None) or getattr(body, "name", None),
        "verification": {"state": "unverified"},
        "contacts": {"email": email_norm, "phone": phone_norm},
        "preferences": {
            "preferred_contact": "phone" if phone_norm else "email",
            "privacy": {"default_anonymous": False, "share_publicly_on_map": True},
            "notifications": {"on_status_change": True, "on_resolution": True},
        },
        "address": {
            "neighborhood": getattr(body, "neighborhood", None),
            "city": getattr(body, "city", None),
            "zone_id": getattr(body, "zone_id", None),
        },
        "stats": {"total_requests": 0},
        "role": body.role,
        "is_active": True,
        "password_hash": hash_password(body.password),
        "created_at": now,
        "deleted": False,
    }

    try:
        res = await users_col.insert_one(doc)
    except DuplicateKeyError:
        return None

    doc["_id"] = res.inserted_id
    return doc


async def get_user(user_id: str):
    doc = await users_collection.find_one({"_id": ObjectId(user_id), "deleted": {"$ne": True}})
    return to_user_out(doc) if doc else None


async def update_user(user_id: str, patch: dict):
    doc = await users_collection.find_one({"_id": ObjectId(user_id), "deleted": {"$ne": True}})
    if not doc:
        return None

    update_doc: dict = {}

    if "full_name" in patch and patch["full_name"] is not None:
        update_doc["full_name"] = patch["full_name"]

    if "role" in patch and patch["role"] is not None:
        update_doc["role"] = patch["role"]

    if "is_active" in patch and patch["is_active"] is not None:
        update_doc["is_active"] = patch["is_active"]

    if "password" in patch and patch["password"]:
        update_doc["password_hash"] = hash_password(patch["password"])

    # phone update -> contacts.phone
    if "phone" in patch:
        new_phone = _phone_norm(patch.get("phone"))
        update_doc["contacts.phone"] = new_phone

        # if preferred_contact is phone but phone removed -> revert to email
        if not new_phone:
            update_doc["preferences.preferred_contact"] = "email"

    # preferred_contact update
    if "preferred_contact" in patch and patch["preferred_contact"] in ("email", "phone"):
        if patch["preferred_contact"] == "phone":
            phone_now = (doc.get("contacts") or {}).get("phone")
            if phone_now:
                update_doc["preferences.preferred_contact"] = "phone"
            # else: ignore (can't choose phone if missing)
        else:
            update_doc["preferences.preferred_contact"] = "email"

    if update_doc:
        await users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": update_doc})

    doc2 = await users_collection.find_one({"_id": ObjectId(user_id), "deleted": {"$ne": True}})
    return to_user_out(doc2) if doc2 else None


async def toggle_user_active(user_id: str):
    doc = await users_collection.find_one({"_id": ObjectId(user_id), "deleted": {"$ne": True}})
    if not doc:
        return None

    new_active = not doc.get("is_active", True)
    await users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": new_active}})

    doc2 = await users_collection.find_one({"_id": ObjectId(user_id), "deleted": {"$ne": True}})
    return to_user_out(doc2) if doc2 else None


async def delete_user(user_id: str):
    res = await users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": {"deleted": True}})
    return res.modified_count == 1


# -------------------------
# Auth helpers
# -------------------------
async def get_user_by_email(users_col, email: str):
    email_norm = _email_norm(email)
    return await users_col.find_one({"contacts.email": email_norm, "deleted": {"$ne": True}})


async def login(email: str, password: str):
    """
    Returns raw mongo doc (has _id). API layer should map using to_user_out().
    """
    email_norm = _email_norm(email)

    doc = await users_collection.find_one({"contacts.email": email_norm, "deleted": {"$ne": True}})
    if not doc:
        return None

    if not doc.get("is_active", True):
        return "inactive"

    if not verify_password(password, doc.get("password_hash", "")):
        return None

    return doc

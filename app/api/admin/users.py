from fastapi import APIRouter, HTTPException
from datetime import datetime

from app.schemas.user import UserCreate, UserUpdate, UserOut
from app.services.users_service import (
    list_users,
    create_user,
    get_user,
    update_user,
    toggle_user_active,
    delete_user,
)
from app.db.mongo import audit_collection, users_collection
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService
from app.db.mongo import team_collection
from bson import ObjectId

from app.utils.mongo import serialize_mongo

audit_repo = AuditRepository(audit_collection)
audit_service = AuditService(audit_repo)

router = APIRouter(prefix="/admin/users", tags=["Admin Users"])


# ========================
# LIST USERS
# ========================
@router.get("", response_model=list[UserOut])
async def get_all(
    q: str | None = None,
    role: str | None = None,
    active: bool | None = None,

):
    return await list_users(q=q, role=role, active=active)


# ========================
# CREATE USER
# ========================
@router.post("", response_model=UserOut)
async def create(data: UserCreate):
    u = await create_user(data)
    if not u:
        raise HTTPException(409, "Email already exists")

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "user.create",
        "actor": {
            "role": "admin",
            "email": "admin@system"
        },
        "entity": {
            "type": "user",
            "id": u["id"],
            "email": u["contacts"]["email"]
        },
        "message": f"Added user ({u['contacts']['email']})",
        "meta": {
            "email": u["contacts"]["email"],
            "role": u["role"],
            "is_active": u["is_active"]
        }
    })

    return u


# ========================
# GET ONE USER
# ========================
@router.get("/{user_id}", response_model=UserOut)
async def one(user_id: str):
    u = await get_user(user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u


# ========================
# UPDATE USER
# ========================
@router.patch("/{user_id}", response_model=UserOut)
async def patch(user_id: str, body: UserUpdate):
    old = await get_user(user_id)
    if not old:
        raise HTTPException(404, "User not found")

    updates = body.model_dump(exclude_unset=True)
    u = await update_user(user_id, updates)

    changes = {}
    for field, new_value in updates.items():
        old_value = old.get(field)
        if old_value != new_value:
            changes[field] = {
                "from": old_value,
                "to": new_value
            }

    if changes:
        await audit_service.log_event({
            "time": datetime.utcnow(),
            "type": "user.update",
            "actor": {
                "role": "admin",
                "email": "admin@system"
            },
            "entity": {
                "type": "user",
                "id": user_id,
                "email": old["email"]
            },
            "message": f"Updated user ({old['email']})",
            "meta": {
                "changes": changes
            }
        })

    return u


# ========================
# ENABLE / DISABLE USER
# ========================
@router.post("/{user_id}/toggle", response_model=UserOut)
async def toggle(user_id: str):
    old = await get_user(user_id)
    if not old:
        raise HTTPException(404, "User not found")

    u = await toggle_user_active(user_id)

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "user.toggle",
        "actor": {
            "role": "admin",
            "email": "admin@system"
        },
        "entity": {
            "type": "user",
            "id": user_id,
            "email": old["email"]  # ✅ CORRECT
        },
        "message": f"{'Enabled' if u['is_active'] else 'Disabled'} user ({old['email']})",
        "meta": {
            "from": old["is_active"],
            "to": u["is_active"]
        }
    })

    return u


# ========================
# DELETE USER
# ========================
@router.delete("/{user_id}")
async def remove(user_id: str):
    old = await get_user(user_id)
    if not old:
        raise HTTPException(404, "User not found")

    # 1️⃣ Soft-delete user
    ok = await delete_user(user_id)
    if not ok:
        raise HTTPException(404, "User not found")

    # 2️⃣ REMOVE USER FROM ALL TEAMS (if staff/admin)
    if old["role"] in ("staff", "admin", "office_employee"):
        await team_collection.update_many(
            {"members": user_id},
            {"$pull": {"members": user_id}}
        )

    # 3️⃣ Audit log
    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "user.delete",
        "actor": {
            "role": "admin",
            "email": "admin@system"
        },
        "entity": {
            "type": "user",
            "id": user_id,
            "email": old["contacts"]["email"]
        },
        "message": f"Deleted user ({old['contacts']['email']})",
        "meta": {
            "role": old["role"]
        }
    })

    return {"success": True}

# @router.post("/{user_id}/verify", response_model=UserOut)
# async def verify_user(user_id: str):
#     user = await users_collection.find_one({"_id": ObjectId(user_id)})
#     if not user:
#         raise HTTPException(404, "User not found")
#
#     if user.get("verification", {}).get("state") == "verified":
#         user["id"] = str(user["_id"])
#         del user["_id"]
#         return user
#
#     await users_collection.update_one(
#         {"_id": ObjectId(user_id)},
#         {
#             "$set": {
#                 "verification.state": "verified",
#                 "verification.verified_at": datetime.utcnow()
#             }
#         }
#     )
#
#     await audit_service.log_event({
#         "time": datetime.utcnow(),
#         "type": "user.verify",
#         "actor": {
#             "role": "admin",
#             "email": "admin@system"
#         },
#         "entity": {
#             "type": "user",
#             "id": user_id
#         },
#         "message": f"User verified ({user.get('full_name')})",
#         "meta": {
#             "email": user.get("contacts", {}).get("email")
#         }
#     })
#
#     # 🔴 FIX HERE
#     user["verification"]["state"] = "verified"
#     user["verification"]["verified_at"] = datetime.utcnow()
#
#     user["id"] = str(user["_id"])
#     del user["_id"]
#
#     return user
@router.post("/{user_id}/verify", response_model=UserOut)
async def verify_user(user_id: str):
    oid = ObjectId(user_id)

    user = await users_collection.find_one({"_id": oid})
    if not user:
        raise HTTPException(404, "User not found")

    # already verified -> still normalize before return
    if user.get("verification", {}).get("state") == "verified":
        user["id"] = str(user["_id"])
        user.pop("_id", None)

        # ✅ normalize email
        if not user.get("email"):
            user["email"] = (user.get("contacts") or {}).get("email")

        return user

    now = datetime.utcnow()

    await users_collection.update_one(
        {"_id": oid},
        {"$set": {"verification.state": "verified", "verification.verified_at": now}},
    )

    # ✅ fetch updated doc (so you return what DB really has)
    user = await users_collection.find_one({"_id": oid})

    await audit_service.log_event({
        "time": now,
        "type": "user.verify",
        "actor": {"role": "admin", "email": "admin@system"},
        "entity": {"type": "user", "id": user_id},
        "message": f"User verified ({user.get('full_name')})",
        "meta": {"email": user.get("email") or (user.get("contacts") or {}).get("email")},
    })

    user["id"] = str(user["_id"])
    user.pop("_id", None)

    # ✅ normalize email again
    if not user.get("email"):
        user["email"] = (user.get("contacts") or {}).get("email")

    return user

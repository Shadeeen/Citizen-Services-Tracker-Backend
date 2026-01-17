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
from app.db.mongo import audit_collection
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService

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
            "email": u["email"]
        },
        "message": f"Added user ({u['email']})",
        "meta": {
            "email": u["email"],
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
            "email": old["email"]
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

    ok = await delete_user(user_id)
    if not ok:
        raise HTTPException(404, "User not found")

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
            "email": old["email"]
        },
        "message": f"Deleted user ({old['email']})",
        "meta": {
            "email": old["email"],
            "role": old["role"]
        }
    })

    return {"success": True}

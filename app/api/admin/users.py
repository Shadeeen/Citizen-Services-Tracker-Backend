from fastapi import APIRouter, HTTPException, Query
from app.schemas.user import UserCreate, UserUpdate, UserOut
from app.services.users_service import (
    list_users, create_user, get_user, update_user,
    toggle_user_active, delete_user
)

router = APIRouter(prefix="/admin/users", tags=["Admin Users"])

@router.get("", response_model=list[UserOut])
async def get_all(
    q: str | None = None,
    role: str | None = None,
    active: bool | None = None,
):
    return await list_users(q=q, role=role, active=active)

@router.post("", response_model=UserOut)
async def create(data: UserCreate):
    u = await create_user(data)
    if not u:
        raise HTTPException(409, "Email already exists")
    return u

@router.get("/{user_id}", response_model=UserOut)
async def one(user_id: str):
    u = await get_user(user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u

@router.patch("/{user_id}", response_model=UserOut)
async def patch(user_id: str, body: UserUpdate):
    u = await update_user(user_id, body.model_dump(exclude_unset=True))
    if not u:
        raise HTTPException(404, "User not found")
    return u

@router.post("/{user_id}/toggle", response_model=UserOut)
async def toggle(user_id: str):
    u = await toggle_user_active(user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u

@router.delete("/{user_id}")
async def remove(user_id: str):
    ok = await delete_user(user_id)
    if not ok:
        raise HTTPException(404, "User not found")
    return {"success": True}

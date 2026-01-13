from fastapi import APIRouter, HTTPException
from app.schemas.sla_policy import (
    SlaPolicyCreate,
    SLAPolicyUpdate,
    SlaPolicyOut,
)
from app.services.sla_service import (
    list_policies,
    create_policy,
    update_policy,
    toggle_active,
    delete_policy,
)

router = APIRouter(prefix="/admin/sla", tags=["Admin SLA"])

@router.get("/", response_model=list[SlaPolicyOut])
async def get_all():
    return await list_policies()

@router.post("/", response_model=SlaPolicyOut)
async def create(data: SlaPolicyCreate):
    return await create_policy(data)

@router.patch("/{policy_id}")
async def update(
    policy_id: str,
    patch: SLAPolicyUpdate,
):
    updated = await update_policy(policy_id, patch.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Policy not found")
    return updated

@router.post("/{policy_id}/toggle", response_model=SlaPolicyOut)
async def toggle(policy_id: str):
    policy = await toggle_active(policy_id)
    if not policy:
        raise HTTPException(404, "Policy not found")
    return policy

@router.delete("/{policy_id}")
async def delete(policy_id: str):
    ok = await delete_policy(policy_id)
    if not ok:
        raise HTTPException(404, "Policy not found")
    return {"success": True}

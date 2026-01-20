from fastapi import APIRouter, HTTPException, Depends
from app.schemas.sla_policy import (
    SlaPolicyCreate,
    SLAPolicyUpdate,
    SlaPolicyOut,
)
from app.services.sla_service import (
    create_sla_for_request,
    update_sla,
    get_sla_by_request,
)
from app.core.security import get_current_admin

router = APIRouter(
    prefix="/admin/requests",
    tags=["Admin SLA"],
)


# ------------------------------------------------------------------
# Create SLA → also TRIAGES the request
# ------------------------------------------------------------------
@router.post("/{request_id}/sla", response_model=SlaPolicyOut)
async def create_sla(
    request_id: str,
    data: SlaPolicyCreate,
    admin=Depends(get_current_admin),
):
    if data.request_id != request_id:
        raise HTTPException(
            status_code=400,
            detail="request_id in path and body must match",
        )

    try:
        return await create_sla_for_request(
            data=data,
            actor={
                "role": "admin",
                "email": admin.email,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------------
# Get SLA for request (VIEW SLA)
# ------------------------------------------------------------------
@router.get("/{request_id}/sla", response_model=SlaPolicyOut)
async def get_sla(request_id: str):
    sla = await get_sla_by_request(request_id)
    if not sla:
        raise HTTPException(status_code=404, detail="SLA not found")
    return sla


# ------------------------------------------------------------------
# Update SLA (allowed ONLY if request already triaged)
# ------------------------------------------------------------------
@router.patch("/{request_id}/sla", response_model=SlaPolicyOut)
async def update_sla_for_request(
    request_id: str,
    patch: SLAPolicyUpdate,
    admin=Depends(get_current_admin),
):
    sla = await get_sla_by_request(request_id)
    if not sla:
        raise HTTPException(status_code=404, detail="SLA not found")

    updated = await update_sla(
        sla_id=str(sla["_id"]),
        patch=patch,
        actor={
            "role": "admin",
            "email": admin.email,
        },
    )
    return updated

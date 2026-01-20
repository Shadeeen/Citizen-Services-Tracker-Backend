from __future__ import annotations

from typing import Any, Dict, Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends

from app.core.security import get_current_admin
from app.models.service_requests import ServiceRequest, ServiceRequestUpdate
from app.services.requests import get_request_by_id, update_request
from app.db.mongo import requests_collection

router = APIRouter(prefix="/admin/requests", tags=["Admin Requests"])


@router.get("", response_model=List[ServiceRequest])
async def list_requests(
    status: Optional[str] = Query(None, regex="^(new|triaged|assigned|in_progress|resolved|closed)$"),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin=Depends(get_current_admin),
):
    filters: Dict[str, Any] = {}
    if status:
        filters["status"] = status
    if category:
        filters["category"] = category

    cursor = (
        requests_collection
        .find(filters)
        .sort("timestamps.created_at", -1)
        .skip(offset)
        .limit(limit)
    )

    docs = []
    async for d in cursor:
        docs.append(d)

    return [ServiceRequest(**doc) for doc in docs]


@router.get("/{request_id}", response_model=ServiceRequest)
async def get_request(
    request_id: str,
    admin=Depends(get_current_admin),
):
    doc = await get_request_by_id(request_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Request not found")
    return ServiceRequest(**doc)


@router.patch("/{request_id}", response_model=ServiceRequest)
async def patch_request(
    request_id: str,
    patch: ServiceRequestUpdate,
    admin=Depends(get_current_admin),
):
    updated = await update_request(
        request_id=request_id,
        patch=patch,
        actor={"role": "admin", "email": admin.email},
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Request not found")
    return ServiceRequest(**updated)

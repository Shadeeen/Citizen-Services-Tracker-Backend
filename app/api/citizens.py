from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from app.models.citizens import Citizen, CitizenCreate
from app.repositories.citizens import CitizenRepository

router = APIRouter(prefix="/citizens", tags=["citizens"])


@router.post("/", response_model=Citizen)
async def create_citizen(payload: CitizenCreate) -> Citizen:
    document = payload.dict()
    document["created_at"] = datetime.utcnow()
    inserted = await CitizenRepository.insert(document)
    return Citizen(**inserted)

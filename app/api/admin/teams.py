from fastapi import APIRouter, HTTPException
from typing import List

from app.schemas.teams import TeamCreate, TeamPatch, TeamOut
from app.services.teams_service import (
    list_teams, get_team, create_team, patch_team, toggle_team, delete_team
)

router = APIRouter(prefix="/admin/teams", tags=["Admin - Teams"])

@router.get("", response_model=List[TeamOut])
def get_all():
    return list_teams()

@router.get("/{team_id}", response_model=TeamOut)
def one(team_id: str):
    try:
        return get_team(team_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("", response_model=TeamOut)
def create(payload: TeamCreate):
    return create_team(payload)

@router.patch("/{team_id}", response_model=TeamOut)
def patch(team_id: str, payload: TeamPatch):
    try:
        return patch_team(team_id, payload)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{team_id}")
def remove(team_id: str):
    try:
        delete_team(team_id)
        return {"ok": True}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{team_id}/toggle", response_model=TeamOut)
def toggle(team_id: str):
    try:
        return toggle_team(team_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

from datetime import date
from typing import Dict, List
from app.schemas.teams import TeamCreate, TeamPatch, TeamOut

# In-memory store (replace later with MongoDB)
_TEAMS: Dict[str, TeamOut] = {
    "t_road_1": TeamOut(
        id="t_road_1",
        name="Road Maintenance Team",
        zones=["ZONE-DT-01", "ZONE-N-03"],
        skills=["pothole", "asphalt_damage"],
        shift="day",
        active=True,
        created_at=str(date.today()),
    ),
    "t_water_1": TeamOut(
        id="t_water_1",
        name="Water Emergency Team",
        zones=["ZONE-W-02"],
        skills=["water_leak"],
        shift="24_7",
        active=True,
        created_at=str(date.today()),
    ),
}

def list_teams() -> List[TeamOut]:
    return list(_TEAMS.values())

def get_team(team_id: str) -> TeamOut:
    if team_id not in _TEAMS:
        raise KeyError("Team not found")
    return _TEAMS[team_id]

def create_team(payload: TeamCreate) -> TeamOut:
    team_id = f"t_{len(_TEAMS) + 1}"
    team = TeamOut(
        id=team_id,
        name=payload.name.strip(),
        zones=payload.zones,
        skills=payload.skills,
        shift=payload.shift,
        active=True,
        created_at=str(date.today()),
    )
    _TEAMS[team_id] = team
    return team

def patch_team(team_id: str, payload: TeamPatch) -> TeamOut:
    team = get_team(team_id)
    data = team.model_dump()

    if payload.name is not None:
        data["name"] = payload.name.strip()
    if payload.zones is not None:
        data["zones"] = payload.zones
    if payload.skills is not None:
        data["skills"] = payload.skills
    if payload.shift is not None:
        data["shift"] = payload.shift
    if payload.active is not None:
        data["active"] = bool(payload.active)

    updated = TeamOut(**data)
    _TEAMS[team_id] = updated
    return updated

def toggle_team(team_id: str) -> TeamOut:
    team = get_team(team_id)
    return patch_team(team_id, TeamPatch(active=not team.active))

def delete_team(team_id: str) -> bool:
    if team_id not in _TEAMS:
        raise KeyError("Team not found")
    del _TEAMS[team_id]
    return True

from pydantic import BaseModel
from typing import List, Optional

class TeamBase(BaseModel):
    name: str
    shift: str
    zones: List[str] = []
    skills: List[str] = []


class TeamCreate(TeamBase):
    members: List[str] = []  # ✅ IDS ONLY


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    shift: Optional[str] = None
    zones: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    members: Optional[List[str]] = None
    active: Optional[bool] = None

class TeamOut(BaseModel):
    id: str
    name: str
    shift: str
    zones: list[str]
    skills: list[str]
    members: list[str]   # ✅ IDS ONLY
    active: bool

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

ShiftType = Literal["day", "24_7"]

class TeamBase(BaseModel):
    name: str = Field(..., min_length=2)
    zones: List[str] = []
    skills: List[str] = []
    shift: ShiftType = "day"

class TeamCreate(TeamBase):
    pass

class TeamPatch(BaseModel):
    name: Optional[str] = None
    zones: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    shift: Optional[ShiftType] = None
    active: Optional[bool] = None

class TeamOut(TeamBase):
    id: str
    active: bool = True
    created_at: Optional[str] = None

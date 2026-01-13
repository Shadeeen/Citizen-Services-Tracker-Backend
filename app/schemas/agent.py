from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional

class AgentCreate(BaseModel):
    full_name: str = Field(min_length=1)
    email: EmailStr
    phone: Optional[str] = None
    team_id: Optional[str] = None
    zones: List[str] = []
    skills: List[str] = []
    shift: str = "Day"         # "Day" | "Night" | "24/7"
    workload_open: int = 0     # open tasks count

class AgentUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    team_id: Optional[str] = None
    zones: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    shift: Optional[str] = None
    workload_open: Optional[int] = None
    active: Optional[bool] = None

class AgentOut(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    team_id: Optional[str] = None
    zones: List[str] = []
    skills: List[str] = []
    shift: str
    workload_open: int = 0
    active: bool = True

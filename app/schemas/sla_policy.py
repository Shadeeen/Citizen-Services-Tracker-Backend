from pydantic import BaseModel
from typing import List, Optional


class EscalationStep(BaseModel):
    after_hours: int
    action: str


class SlaPolicyCreate(BaseModel):
    name: str
    zone: str
    priority: str

    category_code: str
    subcategory_code: str

    target_hours: int
    breach_threshold_hours: int

    escalation_steps: List[EscalationStep]


class SLAPolicyUpdate(BaseModel):
    name: Optional[str] = None
    zone: Optional[str] = None
    priority: Optional[str] = None

    category_code: Optional[str] = None
    subcategory_code: Optional[str] = None

    target_hours: Optional[int] = None
    breach_threshold_hours: Optional[int] = None

    escalation_steps: Optional[List[EscalationStep]] = None


class SlaPolicyOut(BaseModel):
    id: str
    name: str
    zone: str
    priority: str

    category_code: str
    subcategory_code: str

    target_hours: int
    breach_threshold_hours: int

    escalation_steps: List[EscalationStep]
    active: bool

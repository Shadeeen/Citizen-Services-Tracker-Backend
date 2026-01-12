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

class SlaPolicyUpdate(BaseModel):
    name: Optional[str]
    zone: Optional[str]
    priority: Optional[str]

    category_code: Optional[str]
    subcategory_code: Optional[str]

    target_hours: Optional[int]
    breach_threshold_hours: Optional[int]

    escalation_steps: Optional[List[EscalationStep]]
    active: Optional[bool]

class SlaPolicyOut(SlaPolicyCreate):
    id: str
    active: bool

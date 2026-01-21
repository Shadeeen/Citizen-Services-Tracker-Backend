# app/schemas/sla.py
from pydantic import BaseModel
from typing import List, Optional

class EscalationStepIn(BaseModel):
    after_hours: float
    action: str


class SLAPolicyCreateIn(BaseModel):
    team_id: str
    breach_threshold_hours: float
    escalation_steps: List[EscalationStepIn]


class SLAPolicyUpdateIn(BaseModel):
    breach_threshold_hours: Optional[float] = None
    escalation_steps: Optional[List[EscalationStepIn]] = None

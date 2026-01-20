from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class EscalationStep(BaseModel):
    after_hours: int
    action: str


class SlaPolicy(BaseModel):
    name: str

    zone: str
    priority: str
    category: str
    subcategory: str

    target_hours: int
    breach_hours: int

    assigned_team_id: str

    escalation_steps: List[EscalationStep] = []

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True

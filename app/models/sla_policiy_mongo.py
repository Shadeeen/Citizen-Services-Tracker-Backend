# app/models/sla_policy_mongo.py

from datetime import datetime
from typing import List
from app.models.common import PyObjectId

class EscalationStepMongo(dict):
    after_hours: float
    action: str


class SLAPolicyMongo(dict):
    _id: PyObjectId
    request_id: str
    team_id: PyObjectId

    name: str
    zone: str
    priority: str
    category_code: str
    subcategory_code: str

    target_hours: float
    breach_threshold_hours: float
    escalation_steps: List[EscalationStepMongo]

    active: bool
    created_at: datetime
    updated_at: datetime

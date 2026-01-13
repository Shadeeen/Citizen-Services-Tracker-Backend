from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class AuditLog(BaseModel):
    id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    type: str                # auth.login, sla.policy.create
    actor_role: str          # admin, employee
    actor_email: str

    entity_type: str         # sla, user, category
    entity_id: Optional[str]

    message: str

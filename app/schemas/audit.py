from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class AuditActor(BaseModel):
    role: str
    email: str


class AuditEntity(BaseModel):
    type: str
    id: str


class AuditLogOut(BaseModel):
    id: str
    time: datetime
    type: str

    actor: AuditActor
    entity: AuditEntity

    message: str
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)

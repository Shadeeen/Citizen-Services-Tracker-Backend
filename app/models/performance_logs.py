from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.models.common import CSTBaseModel, PyObjectId


class Actor(CSTBaseModel):
    actor_type: str
    actor_id: str


class Event(CSTBaseModel):
    type: str
    by: Actor
    at: datetime
    meta: Dict[str, Any] = Field(default_factory=dict)


class ComputedKPIs(CSTBaseModel):
    resolution_minutes: Optional[float] = None
    sla_target_hours: Optional[float] = None
    sla_state: Optional[str] = None
    escalation_count: int = 0
    breach_reason: Optional[str] = None


class CitizenFeedback(CSTBaseModel):
    rating: Optional[float] = None
    reason_codes: List[str] = Field(default_factory=list)
    comment: Optional[str] = None
    dispute_flag: bool = False
    submitted_at: Optional[datetime] = None


class PerformanceLog(CSTBaseModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    request_id: PyObjectId
    event_stream: List[Event] = Field(default_factory=list)
    computed_kpis: ComputedKPIs = Field(default_factory=ComputedKPIs)
    citizen_feedback: CitizenFeedback = Field(default_factory=CitizenFeedback)


class PerformanceLogCreate(CSTBaseModel):
    request_id: PyObjectId
    event_stream: List[Event] = Field(default_factory=list)

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.models.common import CSTBaseModel, PyObjectId


class CitizenRef(CSTBaseModel):
    citizen_id: Optional[PyObjectId] = None
    anonymous: bool = False
    contact_channel: str = Field("none", regex="^(email|sms|none)$")


class WorkflowState(CSTBaseModel):
    current_state: str
    allowed_next: List[str]
    transition_rules_version: str


class EscalationStep(CSTBaseModel):
    after_hours: float
    action: str


class SLAPolicy(CSTBaseModel):
    policy_id: str
    target_hours: float
    breach_threshold_hours: float
    escalation_steps: List[EscalationStep]


class Timestamps(CSTBaseModel):
    created_at: datetime
    triaged_at: Optional[datetime] = None
    assigned_at: Optional[datetime] = None
    in_progress_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    updated_at: datetime


class Location(CSTBaseModel):
    type: str = Field("Point", regex="^Point$")
    coordinates: List[float]
    address_hint: Optional[str] = None
    zone_id: str


class LocationInput(CSTBaseModel):
    type: str = Field("Point", regex="^Point$")
    coordinates: List[float]
    address_hint: Optional[str] = None


class Duplicates(CSTBaseModel):
    is_master: bool = True
    master_request_id: Optional[str] = None
    linked_duplicates: List[str] = Field(default_factory=list)


class Assignment(CSTBaseModel):
    assigned_agent_id: Optional[PyObjectId] = None
    auto_assign_candidate_agents: List[PyObjectId] = Field(default_factory=list)
    assignment_policy: Optional[str] = None


class EvidenceItem(CSTBaseModel):
    type: str = Field(..., regex="^(photo|video|file)$")
    url: str
    sha256: str
    uploaded_by: str = Field(..., regex="^(citizen|agent|staff)$")
    uploaded_at: datetime


class Internal(CSTBaseModel):
    notes: List[str] = Field(default_factory=list)
    visibility: str = Field("internal_only", regex="^internal_only$")


class ServiceRequestBase(CSTBaseModel):
    citizen_ref: CitizenRef
    category: str
    sub_category: Optional[str] = None
    description: str
    tags: List[str] = Field(default_factory=list)
    status: str = Field("new", regex="^(new|triaged|assigned|in_progress|resolved|closed)$")
    priority: str = Field("P3", regex="^(P1|P2|P3|P4)$")
    workflow: WorkflowState
    sla_policy: SLAPolicy
    timestamps: Timestamps
    location: Location
    duplicates: Duplicates
    assignment: Assignment
    evidence: List[EvidenceItem] = Field(default_factory=list)
    internal: Internal = Field(default_factory=Internal)
    idempotency_key: Optional[str] = None


class ServiceRequest(ServiceRequestBase):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    request_id: str


class ServiceRequestCreate(CSTBaseModel):
    citizen_ref: CitizenRef
    category: str
    sub_category: Optional[str] = None
    description: str
    tags: List[str] = Field(default_factory=list)
    location: LocationInput
    evidence: List[EvidenceItem] = Field(default_factory=list)
    internal_notes: List[str] = Field(default_factory=list)


class ServiceRequestUpdate(CSTBaseModel):
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[str] = Field(None, regex="^(P1|P2|P3|P4)$")


class TransitionRequest(CSTBaseModel):
    target_state: str = Field(..., regex="^(triaged|assigned|in_progress|resolved|closed)$")
    assigned_agent_id: Optional[PyObjectId] = None
    note: Optional[str] = None


class CommentRequest(CSTBaseModel):
    comment_id: str
    parent_comment_id: Optional[str] = None
    message: str

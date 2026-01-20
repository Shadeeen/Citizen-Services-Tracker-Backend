from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.models.common import CSTBaseModel, PyObjectId


class CitizenRef(CSTBaseModel):
    citizen_id: Optional[PyObjectId] = None
    anonymous: bool = False
    contact_channel: str = Field("none", pattern="^(email|sms|none)$")


class EscalationStep(CSTBaseModel):
    after_hours: float
    action: str


class Timestamps(CSTBaseModel):
    created_at: datetime
    triaged_at: Optional[datetime] = None
    assigned_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    updated_at: datetime


class Location(CSTBaseModel):
    type: str = Field("Point", pattern="^Point$")
    coordinates: List[float]
    address_hint: Optional[str] = None
    zone_name: str


class LocationInput(CSTBaseModel):
    type: str = Field("Point", pattern="^Point$")
    coordinates: List[float]
    address_hint: Optional[str] = None
    zone_name: str


class Assignment(CSTBaseModel):
    assigned_team_id: Optional[PyObjectId] = None
    assigned_agent_id: Optional[PyObjectId] = None


class EvidenceItem(CSTBaseModel):
    type: str = Field(..., pattern="^(photo|video|file)$")
    url: str
    uploaded_by: str = Field(..., pattern="^(citizen|agent|staff)$")
    uploaded_at: datetime


class ServiceRequest(ServiceRequestBase := CSTBaseModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    request_id: str

    citizen_ref: CitizenRef
    category: str
    sub_category: Optional[str] = None
    description: str
    tags: List[str] = Field(default_factory=list)

    status: str = Field("new", pattern="^(new|triaged|assigned|resolved|closed)$")
    priority: str = Field("P3", pattern="^(P1|P2|P3|P4)$")

    location: Location
    assignment: Assignment = Field(default_factory=Assignment)

    sla_id: Optional[PyObjectId] = None  # 🔥 LINK TO SLA

    timestamps: Timestamps
    evidence: List[EvidenceItem] = Field(default_factory=list)


class ServiceRequestCreate(CSTBaseModel):
    citizen_ref: CitizenRef
    category: str
    sub_category: Optional[str] = None
    description: str
    tags: List[str] = Field(default_factory=list)
    location: LocationInput
    evidence: List[EvidenceItem] = Field(default_factory=list)


class ServiceRequestUpdate(CSTBaseModel):
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[str] = Field(None, pattern="^(P1|P2|P3|P4)$")

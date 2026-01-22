from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class CitizenRefIn(BaseModel):
    citizen_id: str | None = None
    anonymous: bool = False
    contact_channel: Literal["email", "phone"] = "email"

class GeoPointIn(BaseModel):
    lat: float
    lng: float

class CreateServiceRequestBody(BaseModel):
    citizen_ref: CitizenRefIn
    category: str
    sub_category: str
    description: str
    tags: List[str] = Field(default_factory=list)
    location: GeoPointIn
    address_hint: Optional[str] = None
    zone_name: str

class CreateServiceRequestResponse(BaseModel):
    request_id: str
    status: str
    sla_hint: Optional[str] = None

class UpdateServiceRequestBody(BaseModel):
    category: Optional[str] = None
    sub_category: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    location: Optional[GeoPointIn] = None
    address_hint: Optional[str] = None
    zone_name: Optional[str] = None

class CitizenFeedbackIn(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: Optional[str] = None

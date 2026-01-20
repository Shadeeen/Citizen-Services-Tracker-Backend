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
    zone_name: str   # مثل ZONE-DT-01


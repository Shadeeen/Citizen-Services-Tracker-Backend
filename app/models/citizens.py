from datetime import datetime
from typing import Optional

from pydantic import Field

from app.models.common import CSTBaseModel


class Verification(CSTBaseModel):
    state: str = Field("unverified", regex="^(unverified|verified)$")
    method: Optional[str] = None
    verified_at: Optional[datetime] = None


class Contacts(CSTBaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None


class Notifications(CSTBaseModel):
    on_status_change: bool = True
    on_resolution: bool = True


class Privacy(CSTBaseModel):
    default_anonymous: bool = False
    share_publicly_on_map: bool = False


class Preferences(CSTBaseModel):
    preferred_contact: str = "email"
    language: str = "en"
    privacy: Privacy = Field(default_factory=Privacy)
    notifications: Notifications = Field(default_factory=Notifications)


class Address(CSTBaseModel):
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    zone_id: Optional[str] = None


class Stats(CSTBaseModel):
    total_requests: int = 0
    avg_rating: Optional[float] = None


class Citizen(CSTBaseModel):
    id: Optional[str] = Field(None, alias="_id")
    full_name: Optional[str] = None
    verification: Verification = Field(default_factory=Verification)
    contacts: Contacts = Field(default_factory=Contacts)
    preferences: Preferences = Field(default_factory=Preferences)
    address: Address = Field(default_factory=Address)
    stats: Stats = Field(default_factory=Stats)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CitizenCreate(CSTBaseModel):
    full_name: Optional[str] = None
    contacts: Contacts = Field(default_factory=Contacts)
    preferences: Preferences = Field(default_factory=Preferences)
    address: Address = Field(default_factory=Address)

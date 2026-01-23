from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal, Dict, Any
from datetime import datetime
from app.core.enums import UserRole
import re


# -------------------------
# Nested structures (NEW)
# -------------------------

VerificationState = Literal["unverified", "pending", "verified"]

class VerificationOut(BaseModel):
    state: VerificationState = "unverified"   # ✅ default NOT verified


class ContactsOut(BaseModel):
    email: EmailStr
    phone: Optional[str] = None


class PreferencesPrivacyOut(BaseModel):
    default_anonymous: bool = False
    share_publicly_on_map: bool = True


class PreferencesNotificationsOut(BaseModel):
    on_status_change: bool = True
    on_resolution: bool = True


class PreferencesOut(BaseModel):
    preferred_contact: Literal["email", "phone"] = "email"
    privacy: PreferencesPrivacyOut = Field(default_factory=PreferencesPrivacyOut)
    notifications: PreferencesNotificationsOut = Field(default_factory=PreferencesNotificationsOut)


class AddressOut(BaseModel):
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    zone_id: Optional[str] = None


class StatsOut(BaseModel):
    total_requests: int = 0


# -------------------------
# Requests (INPUT)
# -------------------------

class UserCreate(BaseModel):
    # ✅ نخلي full_name هو الأساسي
    full_name: str = Field(..., alias="name")  # يقبل name من الموبايل كمان
    email: EmailStr
    password: str
    role: str  # أو UserRole
    phone: Optional[str] = Field(default=None, description="E.164 or local format")

    # optional address fields لو بدك
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    zone_id: Optional[str] = None

    # فحص بسيط للـ phone (اختياري تستعمله بالخدمة)
    @staticmethod
    def _is_valid_phone(p: str) -> bool:
        return bool(re.fullmatch(r"^\+?[0-9]{8,15}$", p))

    class Config:
        populate_by_name = True  # يخلي alias شغال (Pydantic v2)



from pydantic import BaseModel, EmailStr, Field, root_validator
from typing import Optional
import re

class UserCreate2(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str
    phone: Optional[str] = Field(default=None, description="E.164 or local format")
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    zone_id: Optional[str] = None

    @root_validator(pre=True)
    def accept_name_alias(cls, values):
        # accept "name" from mobile if "full_name" not provided
        if "full_name" not in values and "name" in values:
            values["full_name"] = values["name"]
        return values

    @staticmethod
    def _is_valid_phone(p: str) -> bool:
        return bool(re.fullmatch(r"^\+?[0-9]{8,15}$", p))


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    phone: Optional[str] = None

    # optional updates for preferences
    preferred_contact: Optional[Literal["email", "phone"]] = None


# -------------------------
# Responses (OUTPUT)
# -------------------------

class UserOut(BaseModel):
    id: str
    full_name: str

    # ✅ ROOT EMAIL (always present)
    email: Optional[str] = None

    # ✅ CONTACTS ARE OPTIONAL
    contacts: Optional[Dict[str, Any]] = None

    verification: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None
    address: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None

    role: str
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user: UserOut
    token: str

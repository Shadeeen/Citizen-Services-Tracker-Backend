# from __future__ import annotations
#
# from datetime import datetime
# from typing import List, Optional
#
# from pydantic import Field
#
# from app.models.common import CSTBaseModel, PyObjectId
#
#
# class EscalationStep(CSTBaseModel):
#     after_hours: float
#     action: str
#
#
# class SLAPolicy(CSTBaseModel):
#     id: Optional[PyObjectId] = Field(None, alias="_id")
#
#     # 🔗 links
#     request_id: str
#     team_id: PyObjectId
#
#     # display
#     name: str
#
#     # matching rules
#     zone: str
#     priority: str = Field(..., pattern="^(P1|P2|P3|P4)$")
#     category_code: str
#     subcategory_code: str
#
#     # sla logic
#     target_hours: float
#     breach_threshold_hours: float
#     escalation_steps: List[EscalationStep] = Field(default_factory=list)
#
#     # lifecycle
#     active: bool = True
#     created_at: datetime
#     updated_at: datetime
#
#
# class SLAPolicyCreate(CSTBaseModel):
#     request_id: str
#     team_id: PyObjectId
#
#     name: str
#     zone: str
#     priority: str = Field(..., pattern="^(P1|P2|P3|P4)$")
#     category_code: str
#     subcategory_code: str
#
#     target_hours: float
#     breach_threshold_hours: float
#     escalation_steps: List[EscalationStep] = Field(default_factory=list)
#
#
# class SLAPolicyUpdate(CSTBaseModel):
#     name: Optional[str] = None
#     target_hours: Optional[float] = None
#     breach_threshold_hours: Optional[float] = None
#     escalation_steps: Optional[List[EscalationStep]] = None
#     active: Optional[bool] = None
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.models.common import CSTBaseModel, PyObjectId


class EscalationStep(CSTBaseModel):
    after_hours: float
    action: str


class SLAPolicy(CSTBaseModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")

    # 🔗 links
    request_id: str
    team_id: Optional[PyObjectId] = None   # ✅ optional (can be assigned later)

    # display
    name: str

    # matching rules
    zone: str
    priority: str = Field(..., pattern="^(P1|P2|P3|P4)$")
    category_code: str
    subcategory_code: str

    # sla logic
    target_hours: float
    breach_threshold_hours: float
    escalation_steps: List[EscalationStep] = Field(default_factory=list)

    # lifecycle
    active: bool = True
    created_at: datetime
    updated_at: datetime


class SLAPolicyCreate(CSTBaseModel):
    request_id: str
    team_id: Optional[PyObjectId] = None   # ✅ optional on create

    name: str
    zone: str
    priority: str = Field(..., pattern="^(P1|P2|P3|P4)$")
    category_code: str
    subcategory_code: str

    target_hours: float
    breach_threshold_hours: float
    escalation_steps: List[EscalationStep] = Field(default_factory=list)


class SLAPolicyUpdate(CSTBaseModel):
    # ✅ allow assigning team later
    team_id: Optional[PyObjectId] = None

    name: Optional[str] = None
    target_hours: Optional[float] = None
    breach_threshold_hours: Optional[float] = None
    escalation_steps: Optional[List[EscalationStep]] = None
    active: Optional[bool] = None

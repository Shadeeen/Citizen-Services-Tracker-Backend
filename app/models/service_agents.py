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
# class GeoFence(CSTBaseModel):
#     type: str = Field("Polygon", regex="^Polygon$")
#     coordinates: List[List[List[float]]]
#
#
# class Coverage(CSTBaseModel):
#     zone_ids: List[str] = Field(default_factory=list)
#     geo_fence: Optional[GeoFence] = None
#
#
# class Shift(CSTBaseModel):
#     day: str
#     start: str
#     end: str
#
#
# class Schedule(CSTBaseModel):
#     timezone: str = "UTC"
#     shifts: List[Shift] = Field(default_factory=list)
#     on_call: bool = False
#
#
# class AgentContacts(CSTBaseModel):
#     phone: Optional[str] = None
#
#
# class ServiceAgent(CSTBaseModel):
#     id: Optional[PyObjectId] = Field(None, alias="_id")
#     agent_code: str
#     name: str
#     department: str
#     skills: List[str] = Field(default_factory=list)
#     coverage: Coverage = Field(default_factory=Coverage)
#     schedule: Schedule = Field(default_factory=Schedule)
#     contacts: AgentContacts = Field(default_factory=AgentContacts)
#     roles: List[str] = Field(default_factory=list)
#     active: bool = True
#     created_at: datetime
#
#
# class ServiceAgentCreate(CSTBaseModel):
#     agent_code: str
#     name: str
#     department: str
#     skills: List[str] = Field(default_factory=list)
#     coverage: Coverage = Field(default_factory=Coverage)
#     schedule: Schedule = Field(default_factory=Schedule)
#     contacts: AgentContacts = Field(default_factory=AgentContacts)
#     roles: List[str] = Field(default_factory=list)
#     active: bool = True

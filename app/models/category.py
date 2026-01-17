from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"

class CategoryDB(BaseModel):
    name: str
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SubcategoryDB(BaseModel):
    category_id: str
    name: str
    priority: Priority
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

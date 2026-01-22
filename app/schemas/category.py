from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.category import Priority

# ---------- Category ----------

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2)

class CategoryResponse(BaseModel):
    id: str
    name: str
    active: bool
    subcategories_count: int

# ---------- Subcategory ----------

class SubcategoryCreate(BaseModel):
    name: str = Field(..., min_length=2)
    priority: Priority

class SubcategoryResponse(BaseModel):
    id: str
    name: str
    priority: Priority
    active: bool

class SubcategoryPatch(BaseModel):
    name: Optional[str] = None
    priority: Optional[Priority] = None
    active: Optional[bool] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None

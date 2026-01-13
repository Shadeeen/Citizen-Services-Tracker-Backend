from typing import List, Optional
from pydantic import BaseModel, Field

class ValidationRules(BaseModel):
    required_fields: List[str] = []
    attachments_min: int = 0
    attachments_max: int = 0
    min_desc_len: int = 0

class SubcategoryBase(BaseModel):
    name: str = Field(..., min_length=2)
    code: str = Field(..., min_length=2)
    validation: ValidationRules = ValidationRules()

class SubcategoryCreate(SubcategoryBase):
    pass

class SubcategoryPatch(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    validation: Optional[ValidationRules] = None
    active: Optional[bool] = None

class SubcategoryOut(SubcategoryBase):
    id: str
    active: bool = True

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2)
    code: str = Field(..., min_length=2)

class CategoryCreate(CategoryBase):
    pass

class CategoryPatch(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None

class CategoryOut(CategoryBase):
    active: bool = True
    subcategories_count: int = 0

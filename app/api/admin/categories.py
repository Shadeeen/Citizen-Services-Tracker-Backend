from fastapi import APIRouter, HTTPException
from typing import List

from app.schemas.categories import (
    CategoryCreate, CategoryPatch, CategoryOut,
    SubcategoryCreate, SubcategoryPatch, SubcategoryOut
)
from app.services.categories_service import (
    list_categories, create_category, patch_category, toggle_category, delete_category,
    list_subcategories, create_subcategory, patch_subcategory, toggle_subcategory, delete_subcategory
)

router = APIRouter(prefix="/admin/categories", tags=["Admin - Categories"])

# Categories
@router.get("", response_model=List[CategoryOut])
def get_all():
    return list_categories()

@router.post("", response_model=CategoryOut)
def create(payload: CategoryCreate):
    try:
        return create_category(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{code}", response_model=CategoryOut)
def patch(code: str, payload: CategoryPatch):
    try:
        return patch_category(code, payload)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{code}")
def remove(code: str):
    try:
        delete_category(code)
        return {"ok": True}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{code}/toggle", response_model=CategoryOut)
def toggle(code: str):
    try:
        return toggle_category(code)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Subcategories
@router.get("/{code}/subcategories", response_model=List[SubcategoryOut])
def get_subs(code: str):
    try:
        return list_subcategories(code)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{code}/subcategories", response_model=SubcategoryOut)
def create_sub(code: str, payload: SubcategoryCreate):
    try:
        return create_subcategory(code, payload)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{code}/subcategories/{sub_code}", response_model=SubcategoryOut)
def patch_sub(code: str, sub_code: str, payload: SubcategoryPatch):
    try:
        return patch_subcategory(code, sub_code, payload)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{code}/subcategories/{sub_code}")
def remove_sub(code: str, sub_code: str):
    try:
        delete_subcategory(code, sub_code)
        return {"ok": True}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{code}/subcategories/{sub_code}/toggle", response_model=SubcategoryOut)
def toggle_sub(code: str, sub_code: str):
    try:
        return toggle_subcategory(code, sub_code)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

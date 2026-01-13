from typing import Dict, List
from app.schemas.categories import (
    CategoryCreate, CategoryPatch, CategoryOut,
    SubcategoryCreate, SubcategoryPatch, SubcategoryOut, ValidationRules
)

# In-memory store
_CATEGORIES: Dict[str, CategoryOut] = {
    "roads": CategoryOut(code="roads", name="Roads", active=True, subcategories_count=2),
    "water": CategoryOut(code="water", name="Water", active=True, subcategories_count=1),
}

_SUBCATS: Dict[str, Dict[str, SubcategoryOut]] = {
    "roads": {
        "pothole": SubcategoryOut(
            id="sub_pothole", name="Pothole", code="pothole", active=True,
            validation=ValidationRules(
                required_fields=["description", "location"],
                attachments_min=1, attachments_max=4, min_desc_len=10
            )
        ),
        "asphalt_damage": SubcategoryOut(
            id="sub_asphalt", name="Asphalt Damage", code="asphalt_damage", active=True,
            validation=ValidationRules(
                required_fields=["description", "location"],
                attachments_min=0, attachments_max=4, min_desc_len=10
            )
        ),
    },
    "water": {
        "water_leak": SubcategoryOut(
            id="sub_water_leak", name="Water Leak", code="water_leak", active=True,
            validation=ValidationRules(
                required_fields=["description", "location"],
                attachments_min=0, attachments_max=3, min_desc_len=10
            )
        )
    }
}

def _recount(cat_code: str):
    cat = _CATEGORIES[cat_code]  # أو كيف عندك

    data = cat.model_dump() if hasattr(cat, "model_dump") else cat.dict()
    data.pop("subcategories_count", None)  # ✅ أهم سطر

    data["subcategories_count"] = len(data.get("subcategories", []))  # أو كيف بتحسبها

    _CATEGORIES[cat_code] = CategoryOut(**data)


# Categories
def list_categories() -> List[CategoryOut]:
    for c in list(_CATEGORIES.keys()):
        _recount(c)
    return list(_CATEGORIES.values())

def create_category(payload: CategoryCreate) -> CategoryOut:
    code = payload.code.strip()
    if code in _CATEGORIES:
        raise ValueError("Category code already exists")
    _CATEGORIES[code] = CategoryOut(code=code, name=payload.name.strip(), active=True, subcategories_count=0)
    _SUBCATS[code] = {}
    return _CATEGORIES[code]

def patch_category(code: str, payload: CategoryPatch) -> CategoryOut:
    if code not in _CATEGORIES:
        raise KeyError("Category not found")
    data = _CATEGORIES[code].model_dump()
    if payload.name is not None:
        data["name"] = payload.name.strip()
    if payload.active is not None:
        data["active"] = bool(payload.active)
    _CATEGORIES[code] = CategoryOut(**data)
    _recount(code)
    return _CATEGORIES[code]

def toggle_category(code: str) -> CategoryOut:
    if code not in _CATEGORIES:
        raise KeyError("Category not found")
    return patch_category(code, CategoryPatch(active=not _CATEGORIES[code].active))

def delete_category(code: str) -> bool:
    if code not in _CATEGORIES:
        raise KeyError("Category not found")
    del _CATEGORIES[code]
    _SUBCATS.pop(code, None)
    return True

# Subcategories
def list_subcategories(cat_code: str) -> List[SubcategoryOut]:
    if cat_code not in _CATEGORIES:
        raise KeyError("Category not found")
    return list(_SUBCATS.get(cat_code, {}).values())

def create_subcategory(cat_code: str, payload: SubcategoryCreate) -> SubcategoryOut:
    if cat_code not in _CATEGORIES:
        raise KeyError("Category not found")
    sub_code = payload.code.strip()
    if sub_code in _SUBCATS.get(cat_code, {}):
        raise ValueError("Subcategory code already exists")
    sub_id = f"sub_{cat_code}_{len(_SUBCATS.get(cat_code, {})) + 1}"
    sub = SubcategoryOut(
        id=sub_id,
        name=payload.name.strip(),
        code=sub_code,
        validation=payload.validation,
        active=True
    )
    _SUBCATS.setdefault(cat_code, {})[sub_code] = sub
    _recount(cat_code)
    return sub

def patch_subcategory(cat_code: str, sub_code: str, payload: SubcategoryPatch) -> SubcategoryOut:
    if cat_code not in _CATEGORIES:
        raise KeyError("Category not found")
    if sub_code not in _SUBCATS.get(cat_code, {}):
        raise KeyError("Subcategory not found")

    sub = _SUBCATS[cat_code][sub_code]
    data = sub.model_dump()

    if payload.name is not None:
        data["name"] = payload.name.strip()
    if payload.validation is not None:
        data["validation"] = payload.validation
    if payload.active is not None:
        data["active"] = bool(payload.active)

    # if code changed → re-key
    new_code = sub_code
    if payload.code is not None:
        new_code = payload.code.strip()

    updated = SubcategoryOut(**data, code=new_code)
    if new_code != sub_code:
        # prevent duplicate
        if new_code in _SUBCATS[cat_code]:
            raise ValueError("Subcategory code already exists")
        del _SUBCATS[cat_code][sub_code]
    _SUBCATS[cat_code][new_code] = updated
    _recount(cat_code)
    return updated

def toggle_subcategory(cat_code: str, sub_code: str) -> SubcategoryOut:
    if sub_code not in _SUBCATS.get(cat_code, {}):
        raise KeyError("Subcategory not found")
    current = _SUBCATS[cat_code][sub_code]
    return patch_subcategory(cat_code, sub_code, SubcategoryPatch(active=not current.active))

def delete_subcategory(cat_code: str, sub_code: str) -> bool:
    if cat_code not in _CATEGORIES:
        raise KeyError("Category not found")
    if sub_code not in _SUBCATS.get(cat_code, {}):
        raise KeyError("Subcategory not found")
    del _SUBCATS[cat_code][sub_code]
    _recount(cat_code)
    return True

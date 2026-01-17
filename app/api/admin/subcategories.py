from fastapi import APIRouter, Depends, HTTPException
from app.db.mongo import get_db
from app.schemas.category import SubcategoryCreate, SubcategoryResponse
from datetime import datetime

router = APIRouter(
    prefix="/admin/categories/{category_id}/subcategories",
    tags=["Subcategories"]
)


@router.get("", response_model=list[SubcategoryResponse])
async def list_subcategories(category_id: str, db=Depends(get_db)):
    subs = []

    async for s in db.subcategory.find({"category_id": category_id, "deleted": False}):
        subs.append({
            "id": str(s["_id"]),
            "name": s["name"],
            "priority": s["priority"],
            "active": s.get("active", True)
        })

    return subs


@router.post("", response_model=SubcategoryResponse)
async def create_subcategory(
        category_id: str,
        payload: SubcategoryCreate,
        db=Depends(get_db)
):
    # ensure category exists
    if not await db.category.find_one({"_id": ObjectId(category_id)}):
        raise HTTPException(status_code=404, detail="Category not found")

    res = await db.subcategory.insert_one({
        "category_id": category_id,
        "name": payload.name,
        "priority": payload.priority,
        "active": True,
        "deleted": False,
        "created_at": datetime.utcnow(),

    })

    return {
        "id": str(res.inserted_id),
        "name": payload.name,
        "priority": payload.priority,
        "active": True
    }


from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from app.db.mongo import get_db
from app.schemas.category import (
    SubcategoryCreate,
    SubcategoryResponse,
)

from pydantic import BaseModel
from typing import Optional
from app.models.category import Priority


# PATCH schema (only editable fields)
class SubcategoryPatch(BaseModel):
    name: Optional[str] = None
    priority: Optional[Priority] = None
    active: Optional[bool] = None


@router.patch("/{subcategory_id}", response_model=SubcategoryResponse)
async def update_subcategory(
        category_id: str,
        subcategory_id: str,
        payload: SubcategoryPatch,
        db=Depends(get_db)
):
    # ensure subcategory exists in this category
    sub = await db.subcategory.find_one({
        "_id": ObjectId(subcategory_id),
        "category_id": category_id, "deleted": False
    })

    if not sub:
        raise HTTPException(status_code=404, detail="Subcategory not found")

    update_data = {}

    if payload.name is not None:
        update_data["name"] = payload.name

    if payload.priority is not None:
        update_data["priority"] = payload.priority

    if payload.active is not None:
        update_data["active"] = payload.active

    if not update_data:
        # nothing to update
        return {
            "id": str(sub["_id"]),
            "name": sub["name"],
            "priority": sub["priority"],
            "active": sub.get("active", True)
        }

    await db.subcategory.update_one(
        {"_id": ObjectId(subcategory_id)},
        {"$set": update_data}
    )

    updated = await db.subcategory.find_one(
        {"_id": ObjectId(subcategory_id)}
    )

    return {
        "id": str(updated["_id"]),
        "name": updated["name"],
        "priority": updated["priority"],
        "active": updated.get("active", True)
    }


@router.post("/{subcategory_id}/toggle", response_model=SubcategoryResponse)
async def toggle_subcategory(
        category_id: str,
        subcategory_id: str,
        db=Depends(get_db)
):
    sub = await db.subcategory.find_one({
        "_id": ObjectId(subcategory_id),
        "category_id": category_id, "deleted": False
    })

    if not sub:
        raise HTTPException(status_code=404, detail="Subcategory not found")

    new_active = not sub.get("active", True)

    await db.subcategory.update_one(
        {"_id": ObjectId(subcategory_id)},
        {"$set": {"active": new_active}}
    )

    return {
        "id": str(sub["_id"]),
        "name": sub["name"],
        "priority": sub["priority"],
        "active": new_active
    }


@router.delete("/{subcategory_id}")
async def delete_subcategory(
        category_id: str,
        subcategory_id: str,
        db=Depends(get_db)
):
    sub = await db.subcategory.find_one({
        "_id": ObjectId(subcategory_id),
        "category_id": category_id,
        "deleted": False
    })

    if not sub:
        raise HTTPException(404, "Subcategory not found")

    await db.subcategory.update_one(
        {"_id": ObjectId(subcategory_id)},
        {"$set": {"deleted": True, "active": False}}
    )

    return {"ok": True}

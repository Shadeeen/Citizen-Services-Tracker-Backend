from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.db.mongo import get_db, audit_collection
from app.schemas.category import (
    SubcategoryCreate,
    SubcategoryResponse,
)
from app.models.category import Priority
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService


audit_service = AuditService(AuditRepository(audit_collection))

router = APIRouter(
    prefix="/admin/categories/{category_id}/subcategories",
    tags=["Admin Subcategories"]
)

# ========================
# LIST
# ========================

@router.get("", response_model=list[SubcategoryResponse])
async def list_subcategories(category_id: str, db=Depends(get_db)):
    subs = []

    async for s in db.subcategory.find({
        "category_id": category_id,
        "deleted": False
    }):
        subs.append({
            "id": str(s["_id"]),
            "name": s["name"],
            "priority": s["priority"],
            "active": s.get("active", True),
        })

    return subs


# ========================
# CREATE
# ========================

@router.post("", response_model=SubcategoryResponse)
async def create_subcategory(
    category_id: str,
    body: SubcategoryCreate,
    db=Depends(get_db)
):
    doc = {
        "category_id": category_id,
        "name": body.name,
        "priority": body.priority,
        "active": True,
        "deleted": False,
        "created_at": datetime.utcnow(),
        "updated_at": None,
    }

    res = await db.subcategory.insert_one(doc)
    sub_id = str(res.inserted_id)

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "subcategory.create",
        "actor": {
            "role": "admin",
            "email": "admin@system",
        },
        "entity": {
            "type": "subcategory",
            "id": sub_id,
        },
        "message": f"Subcategory created ({doc['name']})",
        "meta": {
            "category_id": category_id,
            "name": doc["name"],
            "priority": doc["priority"],
        }
    })

    return {
        "id": sub_id,
        "name": doc["name"],
        "priority": doc["priority"],
        "active": True,
    }


# ========================
# PATCH (UPDATE)
# ========================

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
    before = await db.subcategory.find_one({
        "_id": ObjectId(subcategory_id),
        "category_id": category_id,
        "deleted": False,
    })

    if not before:
        raise HTTPException(404, "Subcategory not found")

    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        return {
            "id": str(before["_id"]),
            "name": before["name"],
            "priority": before["priority"],
            "active": before.get("active", True),
        }

    update_data["updated_at"] = datetime.utcnow()

    await db.subcategory.update_one(
        {"_id": ObjectId(subcategory_id)},
        {"$set": update_data}
    )

    after = await db.subcategory.find_one({"_id": ObjectId(subcategory_id)})

    # build audit diff
    changes = {}
    for field in ["name", "priority", "active"]:
        if field in update_data and before.get(field) != after.get(field):
            changes[field] = {
                "from": before.get(field),
                "to": after.get(field),
            }

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "subcategory.update",
        "actor": {
            "role": "admin",
            "email": "admin@system",
        },
        "entity": {
            "type": "subcategory",
            "id": subcategory_id,
        },
        "message": f"Subcategory updated ({after['name']})",
        "meta": {
            "category_id": category_id,
            "changes": changes,
        }
    })

    return {
        "id": str(after["_id"]),
        "name": after["name"],
        "priority": after["priority"],
        "active": after.get("active", True),
    }


# ========================
# TOGGLE
# ========================

@router.post("/{subcategory_id}/toggle", response_model=SubcategoryResponse)
async def toggle_subcategory(
    category_id: str,
    subcategory_id: str,
    db=Depends(get_db)
):
    sub = await db.subcategory.find_one({
        "_id": ObjectId(subcategory_id),
        "category_id": category_id,
        "deleted": False,
    })

    if not sub:
        raise HTTPException(404, "Subcategory not found")

    prev = sub.get("active", True)
    new_active = not prev

    await db.subcategory.update_one(
        {"_id": ObjectId(subcategory_id)},
        {"$set": {"active": new_active}}
    )

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "subcategory.toggle",
        "actor": {
            "role": "admin",
            "email": "admin@system",
        },
        "entity": {
            "type": "subcategory",
            "id": subcategory_id,
        },
        "message": f"Subcategory {'enabled' if new_active else 'disabled'} ({sub['name']})",
        "meta": {
            "category_id": category_id,
            "from": prev,
            "to": new_active,
        }
    })

    return {
        "id": str(sub["_id"]),
        "name": sub["name"],
        "priority": sub["priority"],
        "active": new_active,
    }


# ========================
# SOFT DELETE
# ========================

@router.delete("/{subcategory_id}")
async def delete_subcategory(
    category_id: str,
    subcategory_id: str,
    db=Depends(get_db)
):
    sub = await db.subcategory.find_one({
        "_id": ObjectId(subcategory_id),
        "category_id": category_id,
        "deleted": False,
    })

    if not sub:
        raise HTTPException(404, "Subcategory not found")

    await db.subcategory.update_one(
        {"_id": ObjectId(subcategory_id)},
        {"$set": {"deleted": True, "active": False}}
    )

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "subcategory.delete",
        "actor": {
            "role": "admin",
            "email": "admin@system",
        },
        "entity": {
            "type": "subcategory",
            "id": subcategory_id,
        },
        "message": f"Subcategory deleted ({sub['name']})",
        "meta": {
            "category_id": category_id,
            "name": sub["name"],
        }
    })

    return {"success": True}

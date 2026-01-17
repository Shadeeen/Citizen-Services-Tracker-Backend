from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime

from app.db.mongo import get_db
from app.schemas.category import CategoryCreate, CategoryResponse
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService
from app.db.mongo import audit_collection

audit_service = AuditService(AuditRepository(audit_collection))

router = APIRouter(
    prefix="/admin/categories",
    tags=["Categories"]
)


@router.get("", response_model=list[CategoryResponse])
async def list_categories(db=Depends(get_db)):
    result = []

    async for c in db.category.find({"deleted": False}):
        count = await db.subcategory.count_documents({
            "category_id": str(c["_id"]),
            "deleted": False
        })

        result.append({
            "id": str(c["_id"]),
            "name": c["name"],
            "active": c.get("active", True),
            "subcategories_count": count
        })

    return result


@router.post("", response_model=CategoryResponse)
async def create_category(data: CategoryCreate, db=Depends(get_db)):
    doc = {
        "name": data.name,
        "active": True,
        "deleted": False,
        "created_at": datetime.utcnow(),
    }

    res = await db.category.insert_one(doc)
    category_id = str(res.inserted_id)

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "category.create",
        "actor": {
            "role": "admin",
            "email": "admin@system",
        },
        "entity": {
            "type": "category",
            "id": category_id,
        },
        "message": f"Category created ({doc['name']})",
        "meta": {
            "name": doc["name"]
        }
    })

    return {
        "id": category_id,
        "name": doc["name"],
        "active": True,
        "subcategories_count": 0
    }


@router.post("/{category_id}/delete")
async def delete_category(category_id: str, db=Depends(get_db)):
    c = await db.category.find_one(
        {"_id": ObjectId(category_id), "deleted": False}
    )
    if not c:
        raise HTTPException(404, "Category not found")

    count = await db.subcategory.count_documents({
        "category_id": category_id,
        "deleted": False
    })

    if count > 0:
        raise HTTPException(400, "Cannot delete category with subcategories")

    await db.category.update_one(
        {"_id": ObjectId(category_id)},
        {"$set": {"deleted": True, "active": False}}
    )

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "category.delete",
        "actor": {
            "role": "admin",
            "email": "admin@system",
        },
        "entity": {
            "type": "category",
            "id": category_id,
        },
        "message": f"Category deleted ({c['name']})",
        "meta": {
            "name": c["name"]
        }
    })

    return {"success": True}

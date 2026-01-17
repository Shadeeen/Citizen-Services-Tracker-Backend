from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from bson.errors import InvalidId

from app.db.mongo import get_db
from app.schemas.category import CategoryCreate, CategoryResponse

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
async def create_category(payload: CategoryCreate, db=Depends(get_db)):
    res = await db.category.insert_one({
        "name": payload.name,
        "active": True,
        "deleted": False,
        "created_at": datetime.utcnow(),
    })

    return {
        "id": str(res.inserted_id),
        "name": payload.name,
        "active": True,
        "subcategories_count": 0
    }


@router.post("/{category_id}/delete")
async def soft_delete_category(category_id: str, db=Depends(get_db)):
    try:
        category_obj_id = ObjectId(category_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid category id")

    category = await db.category.find_one({
        "_id": category_obj_id,
        "deleted": False
    })

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    active_subs = await db.subcategory.count_documents({
        "category_id": category_id,
        "deleted": False
    })

    if active_subs > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete category with subcategories"
        )

    await db.category.update_one(
        {"_id": category_obj_id},
        {"$set": {"deleted": True, "active": False}}
    )

    return {"ok": True}

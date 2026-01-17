from fastapi import APIRouter, Depends
from app.db.mongo import get_db

router = APIRouter(prefix="/admin/skills", tags=["Skills"])

@router.get("")
async def list_skills(db=Depends(get_db)):
    result = []

    async for cat in db.category.find({"deleted": False}):
        subs = []
        async for s in db.subcategory.find({
            "category_id": str(cat["_id"]),
            "deleted": False,
            "active": True
        }):
            subs.append({
                "id": str(s["_id"]),
                "label": s["name"]
            })

        if subs:
            result.append({
                "category": cat["name"],
                "items": subs
            })

    return result

from fastapi import APIRouter, HTTPException
from app.db.mongo import db, sla_rules_collection
from app.models.sla_rules import SLARules

router = APIRouter(prefix="/admin/sla-rules", tags=["Admin SLA Rules"])

@router.get("", response_model=SLARules)
async def get_sla_rules():
    doc = await db["sla_rules"].find_one({})
    if not doc:
        raise HTTPException(status_code=404, detail="SLA rules not found")

    # 🔥 REMOVE MongoDB _id before returning
    doc.pop("_id", None)

    return doc

@router.put("")
async def save_sla_rules(payload: SLARules):
    await sla_rules_collection.delete_many({})
    await sla_rules_collection.insert_one(payload.dict(by_alias=True, exclude={"id"}))
    return {"ok": True}
from app.db.mongo import sla_collection, audit_collection
from app.models.sla_policy import build_sla_doc
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService
from datetime import datetime

audit_repo = AuditRepository(audit_collection)
audit_service = AuditService(audit_repo)


async def list_policies():
    out = []
    async for doc in sla_collection.find():
        doc["id"] = str(doc.pop("_id"))
        out.append(doc)
    return out


async def create_policy(data):
    doc = build_sla_doc(data.dict())
    await sla_collection.insert_one(doc)

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "sla.policy.create",
        "actor": {
            "role": "admin",
            "email": "admin@cst.test",
        },
        "entity": {
            "type": "sla",
            "id": str(doc["_id"]),
        },
        "message": f"Created SLA policy {doc.get('name', '')}",
        "meta": {},
    })

    doc["id"] = str(doc.pop("_id"))
    return doc


async def update_policy(policy_id: str, patch: dict):
    await sla_collection.update_one(
        {"_id": policy_id},
        {"$set": patch},
    )

    doc = await sla_collection.find_one({"_id": policy_id})
    if not doc:
        return None

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "sla.policy.update",
        "actor": {
            "role": "admin",
            "email": "admin@cst.test",
        },
        "entity": {
            "type": "sla",
            "id": policy_id,
        },
        "message": f"Updated SLA policy {doc.get('name', '')}",
        "meta": patch,
    })

    doc["id"] = str(doc.pop("_id"))
    return doc


async def toggle_active(policy_id: str):
    doc = await sla_collection.find_one({"_id": policy_id})
    if not doc:
        return None

    new_state = not doc.get("active", True)

    await sla_collection.update_one(
        {"_id": policy_id},
        {"$set": {"active": new_state}},
    )

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "sla.policy.enable" if new_state else "sla.policy.disable",
        "actor": {
            "role": "admin",
            "email": "admin@cst.test",
        },
        "entity": {
            "type": "sla",
            "id": policy_id,
        },
        "message": (
            f"Enabled SLA policy {doc.get('name')}"
            if new_state
            else f"Disabled SLA policy {doc.get('name')}"
        ),
        "meta": {
            "previous_active": not new_state,
            "current_active": new_state,
        },
    })

    doc["active"] = new_state
    doc["id"] = str(doc.pop("_id"))
    return doc


async def delete_policy(policy_id: str):
    doc = await sla_collection.find_one({"_id": policy_id})
    if not doc:
        return False

    res = await sla_collection.delete_one({"_id": policy_id})
    if res.deleted_count != 1:
        return False

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "sla.policy.delete",
        "actor": {
            "role": "admin",
            "email": "admin@cst.test",
        },
        "entity": {
            "type": "sla",
            "id": policy_id,
        },
        "message": f"Deleted SLA policy {doc.get('name', '')}",
        "meta": {},
    })

    return True

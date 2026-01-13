from fastapi import APIRouter
from app.db.mongo import audit_collection
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin/audit", tags=["Admin - Audit"])

repo = AuditRepository(audit_collection)
service = AuditService(repo)

@router.get("")
async def list_audit_logs():
    return await service.list_logs()

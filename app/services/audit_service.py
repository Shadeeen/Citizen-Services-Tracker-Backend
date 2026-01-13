from app.repositories.audit_repository import AuditRepository

class AuditService:
    def __init__(self, repo: AuditRepository):
        self.repo = repo

    async def list_logs(self):
        return await self.repo.list()

    async def log_event(self, event: dict):
        await self.repo.create(event)

from fastapi import APIRouter, Query
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/admin/analytics", tags=["Admin Analytics"])

service = AnalyticsService()


@router.get("")
async def get_analytics(
    zone: str | None = Query(default=None),
    category: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
):
    return await service.get_dashboard(
        zone=zone,
        category=category,
        date_from=date_from,
        date_to=date_to,
    )

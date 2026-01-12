from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Query

from app.repositories.geo_feeds import GeoFeedRepository
from app.services.analytics import build_heatmap_features, compute_kpis

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/kpis")
async def get_kpis() -> Dict[str, Any]:
    return await compute_kpis()


@router.get("/geofeeds/heatmap")
async def get_heatmap(
    category: str | None = Query(None),
    status: str | None = Query(None),
) -> Dict[str, Any]:
    filters = {"category": category, "status": status}
    features = await build_heatmap_features(filters)
    feed = {
        "feed_name": "heatmap",
        "generated_at": datetime.utcnow(),
        "filters": filters,
        "geojson": {"type": "FeatureCollection", "features": features},
        "aggregation": {
            "method": "point",
            "weight_formula": "priority_weight",
            "tile_hint": "auto",
        },
    }
    stored = await GeoFeedRepository.upsert("heatmap", feed)
    return stored["geojson"]

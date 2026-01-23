from fastapi import APIRouter, Depends, Query
from datetime import datetime, timezone
from collections import Counter
import math
from datetime import timedelta


from app.db.mongo import get_db

router = APIRouter(prefix="/admin/geo-feeds", tags=["Geo Feeds"])

OPEN_STATUSES = {"new", "triaged", "assigned", "in_progress"}


def _cell_center(v: float, step: float) -> float:
    # bucket coordinate into grid, return center
    base = math.floor(v / step) * step
    return base + (step / 2.0)


def _hours_since(dt: datetime, now: datetime) -> float:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    return max(delta.total_seconds() / 3600.0, 0.0)

@router.get("/open-requests-heatmap")
async def open_requests_heatmap(
    window_days: int = Query(30, ge=1, le=365),
    grid_step: float = Query(0.002, gt=0.0001, le=1.0),
    db=Depends(get_db),
):
    now = datetime.now(timezone.utc)

    # we’ll filter by created_at >= now - window_days
    from_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)  # keep it simple
    # better exact window:
    from_dt = now - timedelta(days=window_days)

    cursor = db.service_requests.find(
        {
            "status": {"$in": list(OPEN_STATUSES)},
            "location.type": "Point",
            "location.coordinates": {"$type": "array"},
            "timestamps.created_at": {"$gte": from_dt},
        },
        {
            "location": 1,
            "zone_name": 1,
            "zone": 1,
            "category": 1,
            "sub_category": 1,
            "timestamps": 1,
        },
    )

    buckets = {}  # key -> aggregated data

    async for r in cursor:
        coords = (r.get("location") or {}).get("coordinates") or []
        if len(coords) != 2:
            continue

        lng, lat = coords[0], coords[1]
        if not isinstance(lng, (int, float)) or not isinstance(lat, (int, float)):
            continue

        cx = _cell_center(lng, grid_step)
        cy = _cell_center(lat, grid_step)
        key = (round(cx, 6), round(cy, 6))

        b = buckets.get(key)
        if not b:
            b = {
                "count": 0,
                "zones": [],
                "cats": [],
                "subs": [],
                "ages": [],
            }
            buckets[key] = b

        b["count"] += 1
        b["zones"].append(r.get("zone_name") or r.get("zone"))
        b["cats"].append(r.get("category"))
        b["subs"].append(r.get("sub_category"))

        created_at = (r.get("timestamps") or {}).get("created_at")
        age_h = _hours_since(created_at, now)
        if age_h is not None:
            b["ages"].append(age_h)

    features = []
    for (cx, cy), b in buckets.items():
        zone = Counter([z for z in b["zones"] if z]).most_common(1)
        cat = Counter([c for c in b["cats"] if c]).most_common(1)
        sub = Counter([s for s in b["subs"] if s]).most_common(1)

        avg_age = None
        if b["ages"]:
            avg_age = sum(b["ages"]) / len(b["ages"])


        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [cx, cy]},
                "properties": {
                    "count": b["count"],
                    "weight": b["count"],                 # ✅ your popup field
                    "age_hours": round(avg_age, 2) if avg_age is not None else None,  # ✅ popup field
                    "zone": zone[0][0] if zone else None,
                    "category": cat[0][0] if cat else None,
                    "sub_category": sub[0][0] if sub else None,
                },
            }
        )

    doc = {
        "generated_at": now.isoformat(),
        "window_days": window_days,
        "grid_step": grid_step,
        "total_cells": len(features),
        "geojson": {"type": "FeatureCollection", "features": features},
    }

    # Optional: save latest in geo_feeds collection
    await db.geo_feeds.insert_one(
        {
            "type": "open_requests_heatmap",
            **doc,
            "created_at": now,
        }
    )

    return doc

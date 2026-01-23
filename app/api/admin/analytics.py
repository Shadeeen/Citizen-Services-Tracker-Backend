# from fastapi import APIRouter, Query
# from datetime import datetime, timedelta, timezone
#
# from app.db.mongo import requests_collection
# from app.utils.mongo import serialize_mongo
#
# router = APIRouter(prefix="/admin/analytics", tags=["Analytics"])
#
# def _to_dt(v):
#     if not v:
#         return None
#     if isinstance(v, datetime):
#         return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
#     try:
#         s = str(v)
#         if s.endswith("Z"):
#             s = s[:-1] + "+00:00"
#         dt = datetime.fromisoformat(s)
#         return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
#     except:
#         return None
#
# @router.get("/cohorts")
# async def get_cohorts(
#     days: int = Query(30, ge=1, le=365),
#     limit: int = Query(20, ge=1, le=200),
# ):
#     """
#     Repeat-issue cohorts and recurrence metrics.
#     Cohort signature: zone + category + sub_category.
#     """
#     now = datetime.now(timezone.utc)
#     start = now - timedelta(days=days)
#
#     pipeline = [
#         # time window
#         {
#             "$match": {
#                 "timestamps.created_at": {"$gte": start},
#             }
#         },
#
#         # normalize fields + build cohort key
#         {
#             "$addFields": {
#                 "_created_at": "$timestamps.created_at",
#                 "_zone": {"$ifNull": ["$zone_name", {"$ifNull": ["$sla_policy.zone", ""]}]},
#                 "_cat": {"$ifNull": ["$category", {"$ifNull": ["$sla_policy.category_code", ""]}]},
#                 "_sub": {"$ifNull": ["$sub_category", {"$ifNull": ["$sla_policy.subcategory_code", ""]}]},
#             }
#         },
#         {
#             "$addFields": {
#                 "cohort_key": {
#                     "$concat": [
#                         {"$toString": "$_zone"}, "|",
#                         {"$toString": "$_cat"}, "|",
#                         {"$toString": "$_sub"},
#                     ]
#                 }
#             }
#         },
#
#         # window: previous created_at inside each cohort_key
#         {
#             "$setWindowFields": {
#                 "partitionBy": "$cohort_key",
#                 "sortBy": {"_created_at": 1},
#                 "output": {
#                     "prev_created_at": {
#                         "$shift": {
#                             "output": "$_created_at",
#                             "by": -1
#                         }
#                     }
#                 }
#             }
#         },
#
#         # gap in hours between this and previous event in same cohort
#         {
#             "$addFields": {
#                 "gap_hours": {
#                     "$cond": [
#                         {"$and": [{"$ne": ["$prev_created_at", None]}, {"$ne": ["$_created_at", None]}]},
#                         {
#                             "$divide": [
#                                 {"$subtract": ["$_created_at", "$prev_created_at"]},
#                                 1000 * 60 * 60
#                             ]
#                         },
#                         None
#                     ]
#                 }
#             }
#         },
#
#         # aggregate per cohort
#         {
#             "$group": {
#                 "_id": "$cohort_key",
#                 "zone": {"$first": "$_zone"},
#                 "category": {"$first": "$_cat"},
#                 "sub_category": {"$first": "$_sub"},
#                 "total_requests": {"$sum": 1},
#                 "first_seen": {"$min": "$_created_at"},
#                 "last_seen": {"$max": "$_created_at"},
#                 "avg_gap_hours": {"$avg": "$gap_hours"},
#                 "gaps_count": {
#                     "$sum": {
#                         "$cond": [{"$ne": ["$gap_hours", None]}, 1, 0]
#                     }
#                 },
#             }
#         },
#
#         # only repeated cohorts (>=2)
#         {"$match": {"total_requests": {"$gte": 2}}},
#
#         # sort by volume
#         {"$sort": {"total_requests": -1, "last_seen": -1}},
#         {"$limit": limit},
#
#         # finalize output
#         {
#             "$addFields": {
#                 "days_span": {
#                     "$cond": [
#                         {"$and": [{"$ne": ["$first_seen", None]}, {"$ne": ["$last_seen", None]}]},
#                         {
#                             "$divide": [
#                                 {"$subtract": ["$last_seen", "$first_seen"]},
#                                 1000 * 60 * 60 * 24
#                             ]
#                         },
#                         None
#                     ]
#                 }
#             }
#         },
#         {
#             "$project": {
#                 "_id": 0,
#                 "cohort_key": "$_id",
#                 "zone": 1,
#                 "category": 1,
#                 "sub_category": 1,
#                 "total_requests": 1,
#                 "first_seen": 1,
#                 "last_seen": 1,
#                 "days_span": 1,
#                 "avg_gap_hours": 1,
#                 "gaps_count": 1,
#             }
#         },
#     ]
#
#     rows = []
#     async for doc in requests_collection.aggregate(pipeline):
#         rows.append(serialize_mongo(doc))
#
#     # global summary (how many repeated cohorts exist in window)
#     summary_pipeline = [
#         {"$match": {"timestamps.created_at": {"$gte": start}}},
#         {
#             "$addFields": {
#                 "_zone": {"$ifNull": ["$zone_name", {"$ifNull": ["$sla_policy.zone", ""]}]},
#                 "_cat": {"$ifNull": ["$category", {"$ifNull": ["$sla_policy.category_code", ""]}]},
#                 "_sub": {"$ifNull": ["$sub_category", {"$ifNull": ["$sla_policy.subcategory_code", ""]}]},
#             }
#         },
#         {
#             "$addFields": {
#                 "cohort_key": {
#                     "$concat": [
#                         {"$toString": "$_zone"}, "|",
#                         {"$toString": "$_cat"}, "|",
#                         {"$toString": "$_sub"},
#                     ]
#                 }
#             }
#         },
#         {"$group": {"_id": "$cohort_key", "count": {"$sum": 1}}},
#         {
#             "$group": {
#                 "_id": None,
#                 "total_cohorts": {"$sum": 1},
#                 "repeated_cohorts": {"$sum": {"$cond": [{"$gte": ["$count", 2]}, 1, 0]}},
#                 "total_requests_in_window": {"$sum": "$count"},
#             }
#         },
#         {"$project": {"_id": 0, "total_cohorts": 1, "repeated_cohorts": 1, "total_requests_in_window": 1}},
#     ]
#
#     summary = {"total_cohorts": 0, "repeated_cohorts": 0, "total_requests_in_window": 0, "repeat_rate": 0}
#     async for s in requests_collection.aggregate(summary_pipeline):
#         summary = serialize_mongo(s)
#         break
#
#     tc = summary.get("total_cohorts") or 0
#     rc = summary.get("repeated_cohorts") or 0
#     summary["repeat_rate"] = round((rc / tc) * 100, 2) if tc else 0
#
#     return {"window_days": days, "summary": summary, "cohorts": rows}
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query, Depends
from app.db.mongo import get_db

router = APIRouter(prefix="/admin/analytics", tags=["Admin Analytics"])

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query, Depends
from app.db.mongo import get_db

router = APIRouter(prefix="/admin/analytics", tags=["Admin Analytics"])

@router.get("/cohorts")
async def get_cohorts(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
    db=Depends(get_db),
):
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    col = db["service_requests"]  # ✅ make sure your collection name is EXACTLY "requests"

    base = [
        # ✅ normalize created_at to Date no matter if stored as Date or string
        {"$addFields": {"_created_at": {"$toDate": "$timestamps.created_at"}}},

        # ✅ filter window using normalized date
        {"$match": {"_created_at": {"$gte": start}}},

        # ✅ normalize grouping fields (use fallbacks like your old code)
        {"$addFields": {
            "_zone": {"$ifNull": ["$zone_name", {"$ifNull": ["$zone", {"$ifNull": ["$sla_policy.zone", ""]}]}]},
            "_cat":  {"$ifNull": ["$category", {"$ifNull": ["$sla_policy.category_code", ""]}]},
            "_sub":  {"$ifNull": ["$sub_category", {"$ifNull": ["$sub_category_code", {"$ifNull": ["$sla_policy.subcategory_code", ""]}]}]},
        }},

        {"$group": {
            "_id": {"zone": "$_zone", "category": "$_cat", "sub_category": "$_sub"},
            "total_requests": {"$sum": 1},
            "first_seen": {"$min": "$_created_at"},
            "last_seen": {"$max": "$_created_at"},
        }},

        {"$project": {
            "_id": 0,
            "zone": "$_id.zone",
            "category": "$_id.category",
            "sub_category": "$_id.sub_category",
            "total_requests": 1,
            "first_seen": 1,
            "last_seen": 1,
        }},
    ]

    summary_pipeline = base + [
        {"$group": {
            "_id": None,
            "total_cohorts": {"$sum": 1},
            "repeated_cohorts": {"$sum": {"$cond": [{"$gte": ["$total_requests", 2]}, 1, 0]}},
            "total_requests_in_window": {"$sum": "$total_requests"},
        }},
        {"$project": {"_id": 0, "total_cohorts": 1, "repeated_cohorts": 1, "total_requests_in_window": 1}},
    ]

    list_pipeline = base + [
        {"$sort": {"total_requests": -1, "last_seen": -1}},
        {"$limit": limit},
    ]

    summary_rows = await col.aggregate(summary_pipeline).to_list(length=1)
    summary = summary_rows[0] if summary_rows else {
        "total_cohorts": 0,
        "repeated_cohorts": 0,
        "total_requests_in_window": 0,
    }

    total = summary["total_cohorts"] or 0
    repeated = summary["repeated_cohorts"] or 0
    summary["repeat_rate"] = round((repeated / total) * 100, 2) if total else 0

    cohorts = await col.aggregate(list_pipeline).to_list(length=limit)
    for c in cohorts:
        c["is_repeated"] = (c.get("total_requests") or 0) >= 2
        c["cohort_key"] = f"{c.get('zone','')}|{c.get('category','')}|{c.get('sub_category','')}"

    return {"__backend_version": "NEW_COHORTS_V2", "summary": summary, "cohorts": cohorts}

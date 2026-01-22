from fastapi import APIRouter
from datetime import datetime, timedelta
from collections import defaultdict

from app.db.mongo import requests_collection
from app.db.mongo import users_collection, team_collection
from bson import ObjectId

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


@router.get("/dashboard")
async def admin_dashboard():
    requests = await requests_collection.find({}).to_list(None)

    now = datetime.utcnow()

    # =========================
    # TOTALS
    # =========================
    total_requests = len(requests)

    open_statuses = {"new", "triaged", "assigned", "in_progress"}
    open_requests = sum(1 for r in requests if r.get("status") in open_statuses)

    closed_requests = sum(1 for r in requests if r.get("status") == "closed")
    closed_rate = round((closed_requests / total_requests) * 100, 2) if total_requests else 0

    # =========================
    # AVG RESPONSE TIME (created → triaged)
    # =========================
    response_times = []

    for r in requests:
        ts = r.get("timestamps", {})
        created = ts.get("created_at")
        triaged = ts.get("triaged_at")

        if created and triaged:
            response_times.append((triaged - created).total_seconds() / 60)

    avg_response_time = round(sum(response_times) / len(response_times), 1) if response_times else None

    # =========================
    # SLA PERFORMANCE (COMPUTED)
    # =========================
    sla_ok = sla_at_risk = sla_breached = 0

    for r in requests:
        sla = r.get("sla_policy")
        created = r.get("timestamps", {}).get("created_at")

        if not sla or not created:
            continue

        elapsed_hours = (now - created).total_seconds() / 3600

        if elapsed_hours >= sla["breach_threshold_hours"]:
            sla_breached += 1
        elif elapsed_hours >= sla["target_hours"]:
            sla_at_risk += 1
        else:
            sla_ok += 1

    total_sla = sla_ok + sla_at_risk + sla_breached
    compliance = round((sla_ok / total_sla) * 100, 2) if total_sla else 0

    # =========================
    # STATUS BREAKDOWN
    # =========================
    status_breakdown = {
        "new": 0,
        "triaged": 0,
        "assigned": 0,
        "in_progress": 0,
        "resolved": 0,
        "closed": 0
    }

    for r in requests:
        status = r.get("status", "new")
        if status in status_breakdown:
            status_breakdown[status] += 1

    # =========================
    # PRIORITY DISTRIBUTION
    # =========================
    priority_distribution = defaultdict(int)
    for r in requests:
        if r.get("priority"):
            priority_distribution[r["priority"]] += 1

    # =========================
    # REQUESTS BY CATEGORY + SUBCATEGORY
    # =========================
    categories = {}

    for r in requests:
        cat = r.get("category", "Uncategorized")
        sub = r.get("sub_category")

        if cat not in categories:
            categories[cat] = {
                "category": cat,
                "total": 0,
                "subs": defaultdict(int)
            }

        categories[cat]["total"] += 1
        if sub:
            categories[cat]["subs"][sub] += 1

    requests_by_category = [
        {
            "category": c["category"],
            "total": c["total"],
            "subs": [
                {"name": s, "count": n}
                for s, n in c["subs"].items()
            ]
        }
        for c in categories.values()
    ]

    # =========================
    # TREND (LAST 7 DAYS)
    # =========================
    last_7_days = now - timedelta(days=7)
    trend_map = defaultdict(int)

    for r in requests:
        created = r.get("timestamps", {}).get("created_at")
        if created and created >= last_7_days:
            day = created.date().isoformat()
            trend_map[day] += 1

    trend = [{"date": d, "count": c} for d, c in sorted(trend_map.items())]

    # =========================
    # USER VERIFICATION STATS
    # =========================
    verified_users = await users_collection.count_documents({
        "verification.state": "verified",
        "deleted": False
    })

    unverified_users = await users_collection.count_documents({
        "$or": [
            {"verification.state": {"$ne": "verified"}},
            {"verification": {"$exists": False}}
        ],
        "deleted": False
    })

    teams = await team_collection.find({"deleted": False}).to_list(None)

    team_requests_map = defaultdict(int)

    for r in requests:
        team_id = None

        assigned_team = r.get("assignment", {}).get("assigned_team_id")
        if assigned_team:
            team_id = assigned_team

        else:
            team_id = r.get("sla_policy", {}).get("team_id")

        if team_id:
            team_requests_map[str(team_id)] += 1

    teams_summary = [
        {
            "team_id": str(t["_id"]),
            "name": t.get("name"),
            "requests_count": team_requests_map.get(str(t["_id"]), 0),
            "staff_count": len(t.get("members", [])),
            "active": t.get("active", True),
            "zones": t.get("zones", [])
        }
        for t in teams
    ]

    citizens_count = await users_collection.count_documents({"role": "citizen"})
    staff_count = await users_collection.count_documents({
        "role": "staff",
        "deleted": False
    })

    # =========================
    # ZONE DISTRIBUTION (FIXED)
    # =========================
    zone_distribution = defaultdict(int)

    for r in requests:
        zone = r.get("zone_name")  # ✅ ROOT LEVEL
        if zone:
            zone_distribution[zone] += 1

    zones = [
        {"zone": z, "count": c}
        for z, c in zone_distribution.items()
    ]

    # =========================
    # FINAL RESPONSE
    # =========================
    return {
        "totals": {
            "total_requests": total_requests,
            "open_requests": open_requests,
            "closed_requests": closed_requests,
            "closed_rate": closed_rate,
            "avg_response_time_minutes": avg_response_time
        },
        "sla": {
            "ok": sla_ok,
            "at_risk": sla_at_risk,
            "breached": sla_breached,
            "compliance_percent": compliance
        },
        "trend": trend,
        "priority_distribution": [
            {"priority": p, "count": c}
            for p, c in priority_distribution.items()
        ],
        "status_breakdown": status_breakdown,
        "requests_by_category": requests_by_category,

        "users": {
            "verified": verified_users,
            "unverified": unverified_users,
            "citizens": citizens_count,
            "staff": staff_count},

        "teams": {
            "total": len(teams),
            "per_team": teams_summary
        },

        "zones": zones,

    }

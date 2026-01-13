from datetime import datetime
from app.db.mongo import requests_collection


class AnalyticsService:
    async def get_dashboard(self, zone=None, category=None, date_from=None, date_to=None):
        query = self._build_query(zone, category, date_from, date_to)

        total = await requests_collection.count_documents(query)
        open_count = await requests_collection.count_documents({**query, "status": {"$ne": "closed"}})
        closed = await requests_collection.count_documents({**query, "status": "closed"})

        breached = await requests_collection.count_documents({
            **query,
            "sla_breached": True
        })

        return {
            "summary": {
                "total_requests": total,
                "open_requests": open_count,
                "closed_requests": closed,
                "sla_breached": breached,
                "sla_breached_pct": round((breached / total) * 100, 2) if total else 0,
            },
            "by_status": await self._by_status(query),
            "by_zone": await self._by_zone(query),
            "priority_distribution": await self._by_priority(query),
            "trend": await self._by_day(query),
        }

    # -------------------------
    def _build_query(self, zone, category, date_from, date_to):
        q = {}

        if zone and zone != "all":
            q["zone"] = zone

        if category and category != "all":
            q["category_code"] = category

        if date_from or date_to:
            q["created_at"] = {}

        if date_from:
            q["created_at"]["$gte"] = datetime.fromisoformat(date_from)

        if date_to:
            q["created_at"]["$lte"] = datetime.fromisoformat(date_to)

        return q

    # -------------------------
    async def _by_status(self, base_query):
        pipeline = [
            {"$match": base_query},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]

        data = {}
        async for row in requests_collection.aggregate(pipeline):
            data[row["_id"]] = row["count"]

        return data

    # -------------------------
    async def _by_zone(self, base_query):
        pipeline = [
            {"$match": base_query},
            {"$group": {"_id": "$zone", "count": {"$sum": 1}}},
        ]

        out = []
        async for row in requests_collection.aggregate(pipeline):
            out.append({
                "zone": row["_id"] or "unknown",
                "count": row["count"]
            })
        return out

    # -------------------------
    async def _by_priority(self, base_query):
        pipeline = [
            {"$match": base_query},
            {"$group": {"_id": "$priority", "count": {"$sum": 1}}},
        ]

        data = {}
        async for row in requests_collection.aggregate(pipeline):
            data[row["_id"]] = row["count"]

        return data

    # -------------------------
    async def _by_day(self, base_query):
        pipeline = [
            {"$match": base_query},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]

        out = []
        async for row in requests_collection.aggregate(pipeline):
            out.append({
                "date": row["_id"],
                "count": row["count"]
            })

        return out

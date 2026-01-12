from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.db.mongo import mongo


class ServiceRequestRepository:
    @staticmethod
    async def find_by_request_id(request_id: str) -> Optional[Dict[str, Any]]:
        return await mongo.db.service_requests.find_one({"request_id": request_id})

    @staticmethod
    async def find_by_idempotency_key(key: str) -> Optional[Dict[str, Any]]:
        return await mongo.db.service_requests.find_one({"idempotency_key": key})

    @staticmethod
    async def insert(document: Dict[str, Any]) -> Dict[str, Any]:
        result = await mongo.db.service_requests.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    @staticmethod
    async def update_by_request_id(
        request_id: str, update: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        await mongo.db.service_requests.update_one({"request_id": request_id}, update)
        return await ServiceRequestRepository.find_by_request_id(request_id)

    @staticmethod
    async def find_duplicates(
        category: str,
        center: List[float],
        radius_m: int,
        window_hours: int,
    ) -> List[Dict[str, Any]]:
        since = datetime.utcnow() - timedelta(hours=window_hours)
        cursor = mongo.db.service_requests.find(
            {
                "category": category,
                "timestamps.created_at": {"$gte": since},
                "location": {
                    "$nearSphere": {
                        "$geometry": {"type": "Point", "coordinates": center},
                        "$maxDistance": radius_m,
                    }
                },
            }
        )
        return await cursor.to_list(length=50)

    @staticmethod
    async def add_duplicate_link(
        master_request_id: str, duplicate_request_id: str
    ) -> None:
        await mongo.db.service_requests.update_one(
            {"request_id": master_request_id},
            {
                "$addToSet": {"duplicates.linked_duplicates": duplicate_request_id},
                "$set": {"timestamps.updated_at": datetime.utcnow()},
            },
        )

    @staticmethod
    async def set_duplicate_master(request_id: str, master_request_id: str) -> None:
        await mongo.db.service_requests.update_one(
            {"request_id": request_id},
            {
                "$set": {
                    "duplicates.is_master": False,
                    "duplicates.master_request_id": master_request_id,
                    "timestamps.updated_at": datetime.utcnow(),
                }
            },
        )

    @staticmethod
    async def find_open_requests() -> List[Dict[str, Any]]:
        cursor = mongo.db.service_requests.find(
            {"status": {"$in": ["new", "triaged", "assigned", "in_progress"]}}
        )
        return await cursor.to_list(length=500)

    @staticmethod
    async def list_by_status(status: str, limit: int, offset: int) -> List[Dict[str, Any]]:
        cursor = (
            mongo.db.service_requests.find({"status": status})
            .skip(offset)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    @staticmethod
    async def list_requests(
        filters: Dict[str, Any], limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        cursor = mongo.db.service_requests.find(filters).skip(offset).limit(limit)
        return await cursor.to_list(length=limit)

    @staticmethod
    async def count_workload(agent_id: ObjectId) -> int:
        return await mongo.db.service_requests.count_documents(
            {
                "assignment.assigned_agent_id": agent_id,
                "status": {"$in": ["assigned", "in_progress"]},
            }
        )

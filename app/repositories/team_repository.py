from bson import ObjectId
from datetime import datetime

class TeamRepository:
    def __init__(self, col):
        self.col = col

    def _doc(self, d):
        d["id"] = str(d["_id"])
        del d["_id"]
        return d

    async def list(self):
        cur = self.col.find({"deleted": False})
        return [self._doc(x) async for x in cur]

    async def get(self, team_id: str):
        d = await self.col.find_one({"_id": ObjectId(team_id), "deleted": False})
        return self._doc(d) if d else None

    async def create(self, data: dict):
        data.update({
            "active": True,
            "deleted": False,
            "created_at": datetime.utcnow(),
            "updated_at": None,
        })
        r = await self.col.insert_one(data)
        return await self.get(str(r.inserted_id))

    async def update(self, team_id: str, data: dict):
        data["updated_at"] = datetime.utcnow()
        await self.col.update_one(
            {"_id": ObjectId(team_id), "deleted": False},
            {"$set": data},
        )
        return await self.get(team_id)

    async def toggle(self, team_id: str):
        t = await self.get(team_id)
        if not t:
            return None
        await self.col.update_one(
            {"_id": ObjectId(team_id)},
            {"$set": {"active": not t["active"]}},
        )
        return await self.get(team_id)

    async def delete(self, team_id: str):
        r = await self.col.update_one(
            {"_id": ObjectId(team_id), "deleted": False},
            {"$set": {"deleted": True}},
        )
        return r.modified_count == 1

from bson import ObjectId

class UserRepository:
    def __init__(self, col):
        self.col = col

    async def get_by_ids(self, ids: list[str]):
        if not ids:
            return []

        obj_ids = [ObjectId(x) for x in ids]
        cursor = self.col.find(
            {"_id": {"$in": obj_ids}, "deleted": False},
            {"email": 1, "full_name": 1}
        )

        users = {}
        async for u in cursor:
            users[str(u["_id"])] = {
                "id": str(u["_id"]),
                "email": u["email"],
                "full_name": u.get("full_name"),
            }

        return users

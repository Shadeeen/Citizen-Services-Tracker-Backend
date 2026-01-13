class AuditRepository:
    def __init__(self, collection):
        self.collection = collection

    async def list(self):
        out = []
        async for doc in self.collection.find().sort("time", -1):
            doc["id"] = str(doc.pop("_id"))
            out.append(doc)
        return out

    async def create(self, data: dict):
        await self.collection.insert_one(data)

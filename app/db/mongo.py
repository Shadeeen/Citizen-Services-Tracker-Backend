from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient("mongodb+srv://Shaden:Shaden_04@cluster0.rmqob2j.mongodb.net/cst?appName=Cluster0")
db = client["cst"]

sla_collection = db["sla_policies"]

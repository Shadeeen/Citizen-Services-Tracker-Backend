from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient("mongodb+srv://mohJadallah_db_user:Mohammad_04@cluster0.rmqob2j.mongodb.net/cst?appName=Cluster0")
db = client["cst"]

sla_rules_collection = db["sla_rules"]
sla_collection = db["sla_policies"]
audit_collection = db["audit_logs"]
users_collection = db["users"]
requests_collection=db["service_requests"]
team_collection=db["teams"]
cat_collection = db["category"]
subcategory_collection = db["subcategory"]
service_requests_collection = db["service_requests"]

def get_db():
    return db
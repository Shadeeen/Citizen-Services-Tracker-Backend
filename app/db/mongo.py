from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
import os

# your .env is in the project root (same level as "app/")
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "cst")

if not MONGO_URI:
    raise RuntimeError("Missing MONGO_URI in .env")

client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]
sla_rules_collection = db["sla_rules"]
sla_collection = db["sla_policies"]
audit_collection = db["audit_logs"]
users_collection = db["users"]
requests_collection=db["service_requests"]
team_collection=db["teams"]
cat_collection = db["category"]
subcategory_collection = db["subcategory"]
service_requests_collection = db["service_requests"]
performance_logs_collection = db["performance_logs"]

def get_db():
    return db
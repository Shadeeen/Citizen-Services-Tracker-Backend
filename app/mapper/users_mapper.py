from bson import ObjectId
from datetime import datetime

def oid_str(x):
    return str(x) if isinstance(x, ObjectId) else x

def to_user_out(doc: dict) -> dict:
    # يضمن وجود القيم الافتراضية حتى لو doc ناقص
    verification = doc.get("verification") or {"state": "unverified"}
    contacts = doc.get("contacts") or {"email": doc.get("email", ""), "phone": doc.get("phone")}
    preferences = doc.get("preferences") or {
        "preferred_contact": "email",
        "privacy": {"default_anonymous": False, "share_publicly_on_map": True},
        "notifications": {"on_status_change": True, "on_resolution": True},
    }
    address = doc.get("address") or {"neighborhood": None, "city": None, "zone_id": None}
    stats = doc.get("stats") or {"total_requests": 0}

    return {
        "id": oid_str(doc["_id"]),
        "full_name": doc.get("full_name", doc.get("name", "")),

        "verification": verification,
        "contacts": contacts,
        "preferences": preferences,
        "address": address,
        "stats": stats,

        # keep fields
        "role": doc.get("role", "citizen"),
        "is_active": doc.get("is_active", True),
        "created_at": doc.get("created_at", datetime.utcnow()),
    }

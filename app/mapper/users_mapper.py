# from bson import ObjectId
# from datetime import datetime
#
# def oid_str(x):
#     return str(x) if isinstance(x, ObjectId) else x
#
# def to_user_out(doc: dict) -> dict:
#     # يضمن وجود القيم الافتراضية حتى لو doc ناقص
#     verification = doc.get("verification") or {"state": "unverified"}
#     contacts = doc.get("contacts") or {"email": doc.get("email", ""), "phone": doc.get("phone")}
#     preferences = doc.get("preferences") or {
#         "preferred_contact": "email",
#         "privacy": {"default_anonymous": False, "share_publicly_on_map": True},
#         "notifications": {"on_status_change": True, "on_resolution": True},
#     }
#     address = doc.get("address") or {"neighborhood": None, "city": None, "zone_id": None}
#     stats = doc.get("stats") or {"total_requests": 0}
#
#     return {
#         "id": oid_str(doc["_id"]),
#         "full_name": doc.get("full_name", doc.get("name", "")),
#
#         "verification": verification,
#         "contacts": contacts,
#         "preferences": preferences,
#         "address": address,
#         "stats": stats,
#
#         # keep fields
#         "role": doc.get("role", "citizen"),
#         "is_active": doc.get("is_active", True),
#         "created_at": doc.get("created_at", datetime.utcnow()),
#     }
from bson import ObjectId
from datetime import datetime


def oid_str(x):
    return str(x) if isinstance(x, ObjectId) else x


def to_user_out(doc: dict) -> dict:
    """
    Normalize ALL user documents (citizen / staff / admin)
    into ONE stable API shape.
    """

    # -------------------------
    # EMAIL (CRITICAL)
    # -------------------------
    # citizen -> contacts.email
    # staff/admin -> email
    raw_contacts = doc.get("contacts")

    email = (
        raw_contacts.get("email")
        if isinstance(raw_contacts, dict)
        else doc.get("email")
    )

    contacts = raw_contacts if isinstance(raw_contacts, dict) else None

    # -------------------------
    # OPTIONAL NESTED OBJECTS
    # -------------------------
    verification = doc.get("verification") or {"state": "unverified"}

    preferences = doc.get("preferences") or {
        "preferred_contact": "email",
        "privacy": {
            "default_anonymous": False,
            "share_publicly_on_map": True,
        },
        "notifications": {
            "on_status_change": True,
            "on_resolution": True,
        },
    }

    address = doc.get("address") or {
        "neighborhood": None,
        "city": None,
        "zone_id": None,
    }

    stats = doc.get("stats") or {"total_requests": 0}

    # -------------------------
    # FINAL OUTPUT (API CONTRACT)
    # -------------------------
    return {
        "id": oid_str(doc["_id"]),
        "full_name": doc.get("full_name") or doc.get("name", ""),
        "email": email,                 # ✅ ALWAYS PRESENT
        "contacts": contacts,           # optional, but kept
        "verification": verification,
        "preferences": preferences,
        "address": address,
        "stats": stats,
        "role": doc.get("role", "citizen"),
        "is_active": doc.get("is_active", True),
        "created_at": doc.get("created_at") or datetime.utcnow(),
    }

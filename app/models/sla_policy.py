from uuid import uuid4

def build_sla_doc(data: dict) -> dict:
    return {
        "_id": str(uuid4()),

        "name": data["name"],
        "zone": data["zone"],
        "priority": data["priority"],

        "category_code": data["category_code"],
        "subcategory_code": data["subcategory_code"],

        "target_hours": data["target_hours"],
        "breach_threshold_hours": data["breach_threshold_hours"],

        "escalation_steps": data.get("escalation_steps", []),
        "active": True,
    }

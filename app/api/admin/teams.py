from bson import ObjectId
from fastapi import APIRouter, HTTPException
from datetime import datetime

from app.schemas.team import TeamCreate, TeamUpdate, TeamOut
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService
from app.db.mongo import team_collection, users_collection, audit_collection
from app.repositories.team_repository import TeamRepository
from app.repositories.user_repository import UserRepository
from app.services.team_service import TeamService

team_repo = TeamRepository(team_collection)
user_repo = UserRepository(users_collection)
team_service = TeamService(team_repo, user_repo)


def diff_lists(old: list, new: list):
    old = set(old or [])
    new = set(new or [])
    return {
        "added": list(new - old),
        "removed": list(old - new),
    }


async def resolve_users(user_ids: list[str]):
    if not user_ids:
        return []

    users = await users_collection.find(
        {"_id": {"$in": [ObjectId(uid) for uid in user_ids]}},
        {"email": 1, "full_name": 1}
    ).to_list(None)

    return [
        {
            "id": str(u["_id"]),
            "email": u.get("email"),
            "full_name": u.get("full_name"),
        }
        for u in users
    ]


audit_service = AuditService(AuditRepository(audit_collection))

router = APIRouter(prefix="/admin/teams", tags=["Admin Teams"])


@router.get("", response_model=list[TeamOut])
async def list_teams():
    teams = await team_collection.find(
        {"deleted": False}
    ).to_list(None)

    for t in teams:
        t["id"] = str(t["_id"])
        del t["_id"]

        # 🔒 ENSURE MEMBERS ARE STRINGS
        t["members"] = [str(uid) for uid in t.get("members", [])]

    return teams


@router.post("", response_model=TeamOut)
async def create_team(data: TeamCreate):
    doc = {
        "name": data.name,
        "shift": data.shift,
        "zones": data.zones,
        "skills": data.skills,
        "members": data.members,  # IDS ONLY
        "active": True,
        "deleted": False,
        "created_at": datetime.utcnow(),
        "updated_at": None,
    }

    res = await team_collection.insert_one(doc)
    team_id = str(res.inserted_id)

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "team.create",
        "actor": {
            "role": "admin",
            "email": "admin@system",
        },
        "entity": {
            "type": "team",
            "id": team_id,
        },
        "message": f"Team created ({doc['name']})",
        "meta": {
            "name": doc["name"],
            "shift": doc["shift"],
            "zones": doc["zones"],
            "skills": doc["skills"],
            "members": await resolve_users(doc["members"]),
        }

    })

    doc["id"] = team_id
    return doc


@router.patch("/{team_id}", response_model=TeamOut)
async def update_team(team_id: str, body: TeamUpdate):
    before = await team_collection.find_one(
        {"_id": ObjectId(team_id), "deleted": False}
    )
    if not before:
        raise HTTPException(404, "Team not found")

    updates = body.model_dump(exclude_unset=True)
    updates["updated_at"] = datetime.utcnow()

    await team_collection.update_one(
        {"_id": ObjectId(team_id)},
        {"$set": updates}
    )

    after = await team_collection.find_one({"_id": ObjectId(team_id)})

    changes = {}

    for field in ["name", "shift"]:
        if field in updates and before.get(field) != after.get(field):
            changes[field] = {
                "from": before.get(field),
                "to": after.get(field),
            }

    if "zones" in updates:
        changes["zones"] = diff_lists(before.get("zones", []), after.get("zones", []))

    if "skills" in updates:
        changes["skills"] = diff_lists(before.get("skills", []), after.get("skills", []))

    if "members" in updates:
        diff = diff_lists(before.get("members", []), after.get("members", []))

        changes["members"] = {
            "added": await resolve_users(diff["added"]),
            "removed": await resolve_users(diff["removed"]),
        }

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "team.update",
        "actor": {
            "role": "admin",
            "email": "admin@system",
        },
        "entity": {
            "type": "team",
            "id": team_id,
        },
        "message": f"Team updated ({after['name']})",
        "meta": {
            "changes": changes
        }
    })

    after["id"] = str(after["_id"])
    after["members"] = [str(m) for m in after.get("members", [])]
    del after["_id"]

    return after


@router.post("/{team_id}/toggle", response_model=TeamOut)
async def toggle_team(team_id: str):
    t = await team_repo.get(team_id)
    if not t:
        raise HTTPException(404, "Team not found")

    prev = t["active"]
    t = await team_service.toggle(team_id)

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "team.toggle",
        "actor": {
            "role": "admin",
            "email": "admin@system",
        },
        "entity": {
            "type": "team",
            "id": t["id"],
        },
        "message": f"Team {'enabled' if t['active'] else 'disabled'} ({t['name']})",
        "meta": {
            "from": prev,
            "to": t["active"]
        }
    })

    return t


@router.delete("/{team_id}")
async def delete_team(team_id: str):
    t = await team_repo.get(team_id)
    if not t:
        raise HTTPException(404, "Team not found")

    await team_service.delete(team_id)

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "team.delete",
        "actor": {
            "role": "admin",
            "email": "admin@system",
        },
        "entity": {
            "type": "team",
            "id": team_id,
        },
        "message": f"Team deleted ({t['name']})",
        "meta": {
            "name": t["name"]
        }
    })

    return {"success": True}

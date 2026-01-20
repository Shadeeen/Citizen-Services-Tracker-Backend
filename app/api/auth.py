from fastapi import APIRouter, HTTPException
from datetime import datetime

from app.schemas.user import LoginRequest, LoginResponse, UserCreate
from app.core.enums import UserRole

from app.db.mongo import audit_collection, users_collection
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService

from app.services.users_service import login, create_user, get_user_by_email
from app.mapper.users_mapper import to_user_out

audit_service = AuditService(AuditRepository(audit_collection))

router = APIRouter(prefix="/auth", tags=["Auth"])


def _safe_email_from_user(u: dict) -> str:
    """
    يرجع email سواء كان في structure الجديد (contacts.email)
    أو القديم (email).
    """
    if not isinstance(u, dict):
        return ""
    contacts = u.get("contacts") or {}
    email = contacts.get("email") or u.get("email") or ""
    return str(email)


def _safe_id_from_user(u: dict) -> str:
    """
    يرجع id سواء كان 'id' أو '_id' (ObjectId) أو أي صيغة.
    """
    if not isinstance(u, dict):
        return ""
    if "id" in u and u["id"]:
        return str(u["id"])
    if "_id" in u and u["_id"]:
        return str(u["_id"])
    return ""


# =========================
# 1) Register (Mobile) - Citizen only
# =========================
@router.post("/register", response_model=LoginResponse)
async def register_mobile(body: UserCreate):

    # فقط citizen يسجل من التطبيق
    if body.role != UserRole.citizen:
        raise HTTPException(403, "Only citizens can register from mobile app")

    existing = await get_user_by_email(users_collection, body.email)  # ✅ use contacts.email internally
    if existing:
        raise HTTPException(409, "Email already exists")

    u = await create_user(users_collection, body)
    if not u:
        raise HTTPException(409, "Email already exists")

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "user.register",
        "actor": {
            "role": u.get("role", UserRole.citizen.value),
            "email": _safe_email_from_user(u),
        },
        "entity": {
            "type": "user",
            "id": _safe_id_from_user(u),
        },
        "message": f"New user registered ({_safe_email_from_user(u)})",
        "meta": {
            "role": u.get("role", UserRole.citizen.value),
            "source": "mobile"
        }
    })

    return {"user": to_user_out(u), "token": "dev-token"}  # later JWT


# =========================
# 2) Login (Mobile) - Citizen + Employee only
# =========================
@router.post("/login", response_model=LoginResponse)
async def login_mobile(body: LoginRequest):
    u = await login(body.email, body.password)

    if u == "inactive":
        raise HTTPException(403, "Account disabled")
    if not u:
        raise HTTPException(401, "Invalid credentials")

    # منع admin من الموبايل
    # u ممكن يكون dict فيه role = "admin" أو enum value
    role_val = u.get("role") if isinstance(u, dict) else None
    if role_val == UserRole.admin.value:
        raise HTTPException(403, "Admins must login from website")

    # السماح للموبايل فقط: citizen + staff
    allowed_roles = {UserRole.citizen.value, UserRole.staff.value}
    if role_val not in allowed_roles:
        raise HTTPException(403, "Role not allowed for mobile app")

    # ✅ نحول لهيكل UserOut الجديد قبل audit/response
    user_out = to_user_out(u) if isinstance(u, dict) else u

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "user.login",
        "actor": {
            "role": user_out.get("role", role_val),
            "email": _safe_email_from_user(user_out),
        },
        "entity": {
            "type": "user",
            "id": _safe_id_from_user(user_out),
        },
        "message": f"User logged in ({_safe_email_from_user(user_out)})",
        "meta": {
            "source": "mobile"
        }
    })

    return {"user": user_out, "token": "dev-token"}  # later JWT


# =========================
# 3) Admin Login (Web) - Admin only
# =========================
@router.post("/admin/login", response_model=LoginResponse)
async def login_admin_web(body: LoginRequest):
    u = await login(body.email, body.password)

    if u == "inactive":
        raise HTTPException(403, "Account disabled")
    if not u:
        raise HTTPException(401, "Invalid credentials")

    user_out = to_user_out(u)  # ✅ الآن u فيه _id

    # Audit: email صار داخل contacts
    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "user.login",
        "actor": {
            "role": user_out["role"],
            "email": user_out["contacts"]["email"],
        },
        "entity": {
            "type": "user",
            "id": user_out["id"],
        },
        "message": f"User logged in ({user_out['contacts']['email']})",
        "meta": {"source": "mobile"}
    })

    return {"user": user_out, "token": "dev-token"}

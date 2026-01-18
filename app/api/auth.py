from fastapi import APIRouter, HTTPException
from app.schemas.user import LoginRequest, LoginResponse, UserCreate
from app.services.users_service import login, create_user, get_user_by_email
from app.core.enums import UserRole
from datetime import datetime
from app.db.mongo import audit_collection
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService

audit_service = AuditService(AuditRepository(audit_collection))

router = APIRouter(prefix="/auth", tags=["Auth"])


# =========================
# 1) Register (Mobile) - Citizen only
# =========================
@router.post("/register", response_model=LoginResponse)
async def register_mobile(body: UserCreate):
    # فقط citizen يسجل من التطبيق
    if body.role != UserRole.citizen:
        raise HTTPException(403, "Only citizens can register from mobile app")

    existing = await get_user_by_email(body.email)
    if existing:
        raise HTTPException(409, "Email already exists")

    u = await create_user(body)
    if not u:
        raise HTTPException(409, "Email already exists")

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "user.register",
        "actor": {
            "role": u["role"],
            "email": u["email"],
        },
        "entity": {
            "type": "user",
            "id": u["id"],
        },
        "message": f"New user registered ({u['email']})",
        "meta": {
            "role": u["role"],
            "source": "mobile"
        }
    })

    return {"user": u, "token": "dev-token"}  # later JWT


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
    if u["role"] == UserRole.admin.value:
        raise HTTPException(403, "Admins must login from website")

    # السماح للموبايل فقط: citizen + employee
    allowed_roles = {UserRole.citizen.value, UserRole.staff.value}
    if u["role"] not in allowed_roles:
        raise HTTPException(403, "Role not allowed for mobile app")
    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "user.login",
        "actor": {
            "role": u["role"],
            "email": u["email"],
        },
        "entity": {
            "type": "user",
            "id": u["id"],
        },
        "message": f"User logged in ({u['email']})",
        "meta": {
            "source": "mobile"
        }
    })

    return {"user": u, "token": "dev-token"}  # later JWT


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

    # الويب: فقط admin
    if u["role"] != UserRole.admin.value:
        raise HTTPException(403, "Admins only")

    await audit_service.log_event({
        "time": datetime.utcnow(),
        "type": "admin.login",
        "actor": {
            "role": u["role"],
            "email": u["email"],
        },
        "entity": {
            "type": "user",
            "id": u["id"],
        },
        "message": f"Admin logged in ({u['email']})",
        "meta": {
            "source": "web"
        }
    })

    return {"user": u, "token": "dev-token"}  # later JWT

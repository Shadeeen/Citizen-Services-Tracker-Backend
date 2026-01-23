from fastapi import APIRouter, HTTPException
from datetime import datetime

from app.core.security import verify_password
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

    u = await create_user(body)
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

    return {"user": u, "token": "dev-token"}


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

    role_val = u.get("role") if isinstance(u, dict) else None

    # ✅ FIX: لو staff رجع deleted=true، حاول تختار staff غير محذوف بنفس الايميل
    if role_val == UserRole.staff.value and u.get("deleted") is True:
        # جيب كل staff بهذا الايميل ومرتبين (الأحدث أولاً)
        candidates = await users_collection.find(
            {
                "role": UserRole.staff.value,
                "deleted": {"$ne": True},
                # عدّل المفتاح حسب تخزينك للايميل:
                # إذا عندك contacts.email:
                "contacts.email": body.email
                # إذا الايميل عندك user.email بدلها:
                # "email": body.email
            }
        ).sort("created_at", -1).to_list(10)

        picked = None
        for cand in candidates:
            # لازم تعدل اسم الحقل حسب تخزينك:
            pw_hash = cand.get("password_hash") or cand.get("password")  # حسب نظامك
            if not pw_hash:
                continue
            if verify_password(body.password, pw_hash):
                picked = cand
                break

        if not picked:
            # لا يوجد حساب staff غير محذوف يطابق كلمة المرور
            raise HTTPException(401, "Unauthorized")

        u = picked
        role_val = u.get("role")

    # منع admin من الموبايل
    if role_val == UserRole.admin.value:
        raise HTTPException(403, "Admins must login from website")

    # السماح للموبايل فقط: citizen + staff
    allowed_roles = {UserRole.citizen.value, UserRole.staff.value}
    if role_val not in allowed_roles:
        raise HTTPException(403, "Role not allowed for mobile app")

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
        "meta": {"source": "mobile"}
    })

    return {"user": user_out, "token": "dev-token"}



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

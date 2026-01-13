from fastapi import APIRouter, HTTPException
from app.schemas.user import LoginRequest, LoginResponse, UserOut
from app.services.users_service import login

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/login", response_model=LoginResponse)
async def do_login(body: LoginRequest):
    u = await login(body.email, body.password)
    if u == "inactive":
        raise HTTPException(403, "Account disabled")
    if not u:
        raise HTTPException(401, "Invalid credentials")

    return {"user": u, "token": "dev-token"}  # later JWT

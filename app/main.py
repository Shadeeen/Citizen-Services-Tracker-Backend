from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter, Depends
from app.services.audit_service import AuditService
from app.schemas.audit import AuditLogOut
from typing import List
from app.api.admin import audit
from app.api.admin import analytics


from app.api.admin.sla import router as sla_router
from app.api.admin.audit import router as audit_router
from app.api.admin.users import router as users_router
from app.api.admin.teams import router as teams_router
from app.api.admin.categories import router as categories_router
from app.api.admin import categories, subcategories
from app.api.auth import router as auth_router




app = FastAPI(title="CST Backend (MongoDB)")

app.include_router(sla_router)
app.include_router(audit.router)
app.include_router(analytics.router)
app.include_router(categories.router)
app.include_router(subcategories.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Routers
app.include_router(sla_router)
app.include_router(audit_router)
app.include_router(users_router)
app.include_router(teams_router)
app.include_router(auth_router)


@app.get("/")
def root():
    return {"ok": True, "docs": "/docs"}

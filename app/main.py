from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.admin.audit import router as audit_router
from app.api.admin.users import router as users_router
from app.api.admin.teams import router as teams_router
from app.api.admin import analytics
from app.api.admin import categories, subcategories
from app.api.admin.requests_sla import router as requests_sla_router
from app.api.admin.requests import router as requests_router
from app.api.admin.sla_rules import router as sla_rules_router

from app.api.auth import router as auth_router
from app.api.service_requests import router as service_requests_router


app = FastAPI(title="CST Backend (MongoDB)")

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

# base routers
app.include_router(audit_router)
app.include_router(users_router)
app.include_router(teams_router)
app.include_router(auth_router)

# admin routers (partner)
app.include_router(analytics.router)
app.include_router(categories.router)
app.include_router(subcategories.router)
app.include_router(requests_sla_router)
app.include_router(requests_router)
app.include_router(sla_rules_router)

# service requests (you)
app.include_router(service_requests_router)

# static uploads (evidence)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/")
def root():
    return {"ok": True, "docs": "/docs"}

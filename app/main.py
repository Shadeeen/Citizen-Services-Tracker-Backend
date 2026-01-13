from fastapi import FastAPI
from app.api.admin.sla import router as sla_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter, Depends
from app.services.audit_service import AuditService
from app.schemas.audit import AuditLogOut
from typing import List
from app.api.admin import audit


app = FastAPI(title="CST Backend (MongoDB)")
app.include_router(sla_router)
app.include_router(audit.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



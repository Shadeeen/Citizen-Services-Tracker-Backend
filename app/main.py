from fastapi import FastAPI
from app.api.admin.sla import router as sla_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CST Backend (MongoDB)")
app.include_router(sla_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
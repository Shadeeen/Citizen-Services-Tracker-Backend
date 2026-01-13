# app/db/session.py
from app.db.mongo import db as mongo_db

def get_db():
    """
    FastAPI dependency that returns Mongo database instance
    """
    return mongo_db

# app/core/security.py
from fastapi import Depends, HTTPException, status, Request
from passlib.context import CryptContext

pwd = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

def hash_password(password: str) -> str:
    # bcrypt hard limit: 72 BYTES
    if isinstance(password, str):
        password = password.encode("utf-8")
    password = password[:72]
    return pwd.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    if isinstance(password, str):
        password = password.encode("utf-8")
    password = password[:72]
    return pwd.verify(password, hashed)


# app/core/security.py

from fastapi import Request, HTTPException, status

def get_current_admin(request: Request):
    """
    TEMP admin guard.
    Replace later with JWT role validation.
    """
    role = request.headers.get("X-Role", "admin")

    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    # minimal admin object
    return type("Admin", (), {"email": "admin@cst.test"})



# def require_admin(request: Request):
#     """
#     Temporary admin guard.
#     Later replace with JWT role validation.
#     """
#
#     # Example: frontend already logs in as admin
#     # For now, we trust the session
#     user_role = request.headers.get("X-Role", "admin")
#
#     if user_role != "admin":
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Admin privileges required"
#         )


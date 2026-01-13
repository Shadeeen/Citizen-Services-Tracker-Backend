# app/core/security.py
from fastapi import Depends, HTTPException, status, Request

def require_admin(request: Request):
    """
    Temporary admin guard.
    Later replace with JWT role validation.
    """

    # Example: frontend already logs in as admin
    # For now, we trust the session
    user_role = request.headers.get("X-Role", "admin")

    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    return {
        "role": "admin",
        "email": "admin@cst.test"
    }

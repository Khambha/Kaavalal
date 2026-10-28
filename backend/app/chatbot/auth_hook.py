"""THE ONE PLACE TO CONNECT THUNAI TO KAAVALAL'S AUTHENTICATION MODULE (modules 2 and 3).

Return the logged-in user's integer id, or None for anonymous visitors.
Anonymous users can still use alerts, shelters, risk, rainfall and safety guidance.
Only "my incident" lookups need a user, and they are always limited to that user's own reports.

Replace the body below with your existing JWT logic. Example, if you already have a decode function:

    from app.auth.security import decode_access_token   # your existing helper

    def get_optional_user_id(request: Request) -> Optional[int]:
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            return None
        try:
            payload = decode_access_token(header[7:])
            return int(payload["sub"])
        except Exception:
            return None
"""
from typing import Optional

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.routers.auth import ALGORITHM, SECRET_KEY


def get_optional_user_id(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[int]:
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return None

    try:
        payload = jwt.decode(
            authorization[7:].strip(),
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None

    user = db.get(User, user_id)
    return user.id if user and user.status == "active" else None

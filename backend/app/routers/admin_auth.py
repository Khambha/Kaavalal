import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.admin_user import AdminUser

load_dotenv()
router = APIRouter(prefix="/api/admin-auth", tags=["Admin Authentication"])
bearer_scheme = HTTPBearer()
password_hash = PasswordHash.recommended()
SECRET_KEY = os.getenv("ADMIN_JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("ADMIN_JWT_SECRET_KEY is missing. Configure it in backend/.env.")


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AdminPasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)


def admin_public(admin: AdminUser):
    return {
        "id": admin.id,
        "full_name": admin.full_name,
        "email": admin.email,
        "is_active": admin.is_active,
        "must_change_password": admin.must_change_password,
        "created_at": admin.created_at,
    }


def create_admin_token(admin: AdminUser):
    payload = {
        "sub": str(admin.id),
        "type": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "admin":
            raise ValueError("Wrong token type")
        admin_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired admin token.")
    admin = db.get(AdminUser, admin_id)
    if not admin or not admin.is_active:
        raise HTTPException(status_code=401, detail="Admin account is unavailable.")
    return admin


@router.post("/login")
def login(data: AdminLoginRequest, db: Session = Depends(get_db)):
    email = str(data.email).strip().lower()
    admin = db.query(AdminUser).filter(AdminUser.email == email).first()
    if not admin or not password_hash.verify(data.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not admin.is_active:
        raise HTTPException(status_code=403, detail="This admin account is inactive.")
    return {"access_token": create_admin_token(admin), "token_type": "bearer", "admin": admin_public(admin)}


@router.get("/me")
def get_me(admin: AdminUser = Depends(get_current_admin)):
    return admin_public(admin)


@router.post("/change-password")
def change_password(
    data: AdminPasswordUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    if not password_hash.verify(data.current_password, admin.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    admin.hashed_password = password_hash.hash(data.new_password)
    admin.must_change_password = False
    db.commit()
    return {"message": "Password updated."}

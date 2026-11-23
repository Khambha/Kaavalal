from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.admin_user import AdminUser
from app.core.config import settings
from app.core.rate_limit import get_login_email_key, limiter
from app.services.login_protection import clear_failed_logins, email_digest, is_locked, record_failed_login

router = APIRouter(prefix="/api/admin-auth", tags=["Admin Authentication"])
bearer_scheme = HTTPBearer()
password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash(os.urandom(32).hex())
SECRET_KEY = settings.ADMIN_JWT_SECRET_KEY


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
@limiter.limit("30/minute")
@limiter.limit("10/minute", key_func=get_login_email_key)
def login(request: Request, data: AdminLoginRequest, db: Session = Depends(get_db)):
    email = str(data.email).strip().lower()
    digest = email_digest(email, SECRET_KEY)
    if is_locked(db, "admin", digest):
        password_hash.verify(data.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    admin = db.query(AdminUser).filter(AdminUser.email == email).first()
    password_valid = password_hash.verify(data.password, admin.hashed_password if admin else DUMMY_PASSWORD_HASH)
    if not admin or not password_valid:
        record_failed_login(db, "admin", digest)
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    clear_failed_logins(db, "admin", digest)
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

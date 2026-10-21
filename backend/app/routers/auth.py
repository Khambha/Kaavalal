import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.schemas.auth import (
    SignupRequest,
    LoginRequest,
    UserResponse,
    TokenResponse,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing. Configure it in your backend environment."
    )

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30


# -------------------- JWT TOKEN --------------------

def create_access_token(user: User):
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": expire,
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# -------------------- CURRENT USER --------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token.",
        )

    user = db.get(User, user_id)

    if not user or user.status != "active":
        raise HTTPException(
            status_code=401,
            detail="Account not available or awaiting approval.",
        )

    return user


def require_admin(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access required.",
        )

    return user


# -------------------- SIGNUP --------------------

@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    email = str(data.email).lower()

    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    organization_id = None
    rescuer_id = None

    if data.role == "rescuer":
        if not data.organization_code or not data.organization_code.strip():
            raise HTTPException(
                status_code=400,
                detail="Organization code is required for rescuers.",
            )

        if not data.rescuer_id or not data.rescuer_id.strip():
            raise HTTPException(
                status_code=400,
                detail="Rescuer ID is required.",
            )

        organization_code = data.organization_code.strip().upper()

        organization = (
            db.query(Organization)
            .filter(
                Organization.organization_code == organization_code,
                Organization.is_active.is_(True),
            )
            .first()
        )

        if not organization:
            raise HTTPException(
                status_code=400,
                detail="Invalid or inactive organization code.",
            )

        organization_id = organization.id
        rescuer_id = data.rescuer_id.strip()

    user = User(
        full_name=data.full_name.strip(),
        email=email,
        hashed_password=password_hash.hash(data.password),
        role=data.role,
        district=data.district.strip(),
        nearest_lac=data.nearest_lac.strip(),
        organization_id=organization_id,
        rescuer_id=rescuer_id,
        status="pending" if data.role == "rescuer" else "active",
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user


# -------------------- LOGIN --------------------

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    email = str(data.email).lower()

    user = db.query(User).filter(User.email == email).first()

    if not user or not password_hash.verify(
        data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=403,
            detail="Your account is awaiting administrator approval or is inactive.",
        )

    access_token = create_access_token(user)

    return TokenResponse(access_token=access_token)


# -------------------- CURRENT USER PROFILE --------------------

@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user


# -------------------- ADMIN: PENDING RESCUERS --------------------

@router.get(
    "/admin/pending-rescuers",
    response_model=list[UserResponse],
)
def get_pending_rescuers(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return (
        db.query(User)
        .filter(
            User.role == "rescuer",
            User.status == "pending",
        )
        .all()
    )


# -------------------- ADMIN: APPROVE RESCUER --------------------

@router.patch(
    "/admin/rescuers/{user_id}/approve",
    response_model=UserResponse,
)
def approve_rescuer(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)

    if not user or user.role != "rescuer":
        raise HTTPException(
            status_code=404,
            detail="Rescuer account not found.",
        )

    if user.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="This rescuer is not awaiting approval.",
        )

    user.status = "active"
    db.commit()
    db.refresh(user)

    return user


# -------------------- ADMIN: REJECT RESCUER --------------------

@router.patch(
    "/admin/rescuers/{user_id}/reject",
    response_model=UserResponse,
)
def reject_rescuer(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)

    if not user or user.role != "rescuer":
        raise HTTPException(
            status_code=404,
            detail="Rescuer account not found.",
        )

    if user.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="This rescuer is not awaiting approval.",
        )

    user.status = "rejected"
    db.commit()
    db.refresh(user)

    return user
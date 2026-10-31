import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from pathlib import Path
from dotenv import load_dotenv
import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.password_reset_token import PasswordResetToken
from app.services.password_reset_email import password_reset_email_configured, send_password_reset_email
from app.schemas.auth import (
    ForgotPasswordRequest,
    SignupRequest,
    LoginRequest,
    ResetPasswordRequest,
    UserResponse,
    TokenResponse,
)
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class AvailabilityUpdate(BaseModel):
    is_available: bool

password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer()

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Load environment variables from backend/.env
ENV_FILE = BACKEND_DIR / ".env"
load_dotenv(ENV_FILE)

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        f"JWT_SECRET_KEY is missing. Please check: {ENV_FILE}"
    )

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30
PASSWORD_RESET_EXPIRE_MINUTES = 30
PASSWORD_RESET_COOLDOWN_SECONDS = 60
logger = logging.getLogger(__name__)


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


@router.post("/forgot-password")
def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    generic_message = "If an account matches that email, password reset instructions will be sent."
    if not password_reset_email_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email is not configured yet. Contact your system administrator.",
        )

    email = str(data.email).strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"message": generic_message}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    recent = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.created_at >= now - timedelta(seconds=PASSWORD_RESET_COOLDOWN_SECONDS),
    ).first()
    if recent:
        return {"message": generic_message}

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).delete(synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    token_record = PasswordResetToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        expires_at=now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES),
        created_at=now,
    )
    db.add(token_record)
    db.commit()

    base_url = os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
    reset_url = f"{base_url}/reset-password#{urlencode({'token': raw_token})}"
    background_tasks.add_task(send_password_reset_email_safely, email, reset_url, token_record.id)
    return {"message": generic_message}


def send_password_reset_email_safely(recipient: str, reset_url: str, token_record_id: int):
    try:
        send_password_reset_email(recipient, reset_url)
    except Exception:
        logger.exception("Password reset email delivery failed")
        db = SessionLocal()
        try:
            token_record = db.get(PasswordResetToken, token_record_id)
            if token_record:
                db.delete(token_record)
                db.commit()
        finally:
            db.close()


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(data.token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > now,
    ).first()
    if not token_record:
        raise HTTPException(status_code=400, detail="This reset link is invalid or expired. Request a new one.")

    user = db.get(User, token_record.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="This reset link is invalid or expired. Request a new one.")

    user.hashed_password = password_hash.hash(data.new_password)
    token_record.used_at = now
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.id != token_record.id,
    ).delete(synchronize_session=False)
    db.commit()
    return {"message": "Password updated. You can now sign in with your new password."}
# -------------------- CURRENT USER PROFILE --------------------

@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me/availability")
def set_my_availability(
    data: AvailabilityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in {"rescuer", "responder"}:
        raise HTTPException(status_code=403, detail="Only responders can change availability.")
    user.is_available = data.is_available
    db.commit()
    db.refresh(user)
    return {"is_available": user.is_available}

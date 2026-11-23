from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from app.core.database import Base


class LoginAttempt(Base):
    """Hashed per-account failed-login state for a short lockout window."""

    __tablename__ = "login_attempts"
    __table_args__ = (
        UniqueConstraint("account_type", "email_digest", name="uq_login_attempt_account_email"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_type = Column(String(16), nullable=False)
    email_digest = Column(String(64), nullable=False)
    failed_attempts = Column(Integer, nullable=False, default=0)
    window_started_at = Column(DateTime, nullable=True)
    locked_until = Column(DateTime, nullable=True)

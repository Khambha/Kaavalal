"""Persistent failed-login tracking shared by citizen and admin authentication."""
import hashlib
import hmac
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app.models.login_attempt import LoginAttempt

MAX_FAILED_LOGINS = 5
FAILURE_WINDOW = timedelta(minutes=10)
LOCKOUT_DURATION = timedelta(minutes=10)


def email_digest(email: str, signing_key: str) -> str:
    normalized = email.strip().lower().encode("utf-8")
    return hmac.new(signing_key.encode("utf-8"), normalized, hashlib.sha256).hexdigest()


def is_locked(db, account_type: str, digest: str, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    row = db.query(LoginAttempt).filter_by(account_type=account_type, email_digest=digest).first()
    return bool(row and row.locked_until and row.locked_until > now)


def _locked_row(db, account_type: str, digest: str):
    row = (db.query(LoginAttempt)
           .filter_by(account_type=account_type, email_digest=digest)
           .with_for_update()
           .first())
    if row:
        return row
    row = LoginAttempt(account_type=account_type, email_digest=digest)
    db.add(row)
    try:
        db.flush()
        return row
    except IntegrityError:
        db.rollback()
        return (db.query(LoginAttempt)
                .filter_by(account_type=account_type, email_digest=digest)
                .with_for_update()
                .first())


def record_failed_login(db, account_type: str, digest: str, now: datetime | None = None) -> bool:
    """Record one failure. Return True when this failure starts the lockout."""
    now = now or datetime.utcnow()
    row = _locked_row(db, account_type, digest)
    if row is None:
        return False
    if row.locked_until and row.locked_until > now:
        db.commit()
        return True
    if not row.window_started_at or now - row.window_started_at >= FAILURE_WINDOW:
        row.window_started_at = now
        row.failed_attempts = 0
    row.failed_attempts += 1
    locked = row.failed_attempts >= MAX_FAILED_LOGINS
    if locked:
        row.locked_until = now + LOCKOUT_DURATION
    db.commit()
    return locked


def clear_failed_logins(db, account_type: str, digest: str) -> None:
    row = db.query(LoginAttempt).filter_by(account_type=account_type, email_digest=digest).first()
    if row:
        row.failed_attempts = 0
        row.window_started_at = None
        row.locked_until = None
        db.commit()

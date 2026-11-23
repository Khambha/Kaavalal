from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.login_attempt import LoginAttempt
from app.services.login_protection import (
    clear_failed_logins,
    email_digest,
    is_locked,
    record_failed_login,
)


def test_lockout_starts_after_five_failures_and_expires_after_ten_minutes():
    engine = create_engine("sqlite://")
    LoginAttempt.__table__.create(engine)
    now = datetime(2026, 11, 23, 12, 0, 0)
    digest = email_digest("Citizen@Example.com", "test-signing-key")

    with Session(engine) as db:
        assert not is_locked(db, "citizen", digest, now)
        for _ in range(4):
            assert not record_failed_login(db, "citizen", digest, now)
        assert record_failed_login(db, "citizen", digest, now)
        assert is_locked(db, "citizen", digest, now + timedelta(minutes=9))
        assert not is_locked(db, "citizen", digest, now + timedelta(minutes=10))

    engine.dispose()


def test_successful_login_clears_failed_attempt_state():
    engine = create_engine("sqlite://")
    LoginAttempt.__table__.create(engine)
    now = datetime(2026, 11, 23, 12, 0, 0)
    digest = email_digest("Citizen@Example.com", "test-signing-key")

    with Session(engine) as db:
        for _ in range(5):
            record_failed_login(db, "citizen", digest, now)
        clear_failed_logins(db, "citizen", digest)
        assert not is_locked(db, "citizen", digest, now)
        row = db.query(LoginAttempt).filter_by(account_type="citizen", email_digest=digest).one()
        assert row.failed_attempts == 0
        assert row.locked_until is None

    engine.dispose()

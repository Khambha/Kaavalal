"""Privately bootstrap the first AdminUser from a trusted terminal.

From the backend directory run: python -m app.create_admin
There is deliberately no public administrator signup endpoint.
"""

from getpass import getpass

from pwdlib import PasswordHash
from sqlalchemy import func

from app.core.database import Base, SessionLocal, engine
from app.models import Location, WeatherData, RainfallData, HazardData, RiskData
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser
from app.models.alert import Alert
from app.models.help_request import HelpRequest
from app.models.organization import Organization
from app.models.user import User


def main():
    Base.metadata.create_all(bind=engine)
    email = input("Initial administrator email: ").strip().lower()
    full_name = input("Administrator name: ").strip()
    password = getpass("Password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if not email or "@" not in email:
        raise SystemExit("Enter a valid email address.")
    if len(full_name) < 2:
        raise SystemExit("Enter the administrator's name.")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    db = SessionLocal()
    try:
        if db.query(AdminUser).filter(func.lower(AdminUser.email) == email).first():
            raise SystemExit("An admin account with that email already exists.")
        if db.query(AdminUser.id).count():
            raise SystemExit("Admin accounts already exist. Add future admins in the private admin website.")
        admin = AdminUser(
            full_name=full_name,
            email=email,
            hashed_password=PasswordHash.recommended().hash(password),
            is_active=True,
            must_change_password=False,
        )
        db.add(admin)
        db.commit()
        print(f"Initial admin account created for {email}.")
        print("Open the private admin website and sign in with these credentials.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

"""Shared SlowAPI limiter for API endpoints."""
import hashlib
import json

from slowapi import Limiter
from slowapi.util import get_remote_address


limiter = Limiter(key_func=get_remote_address)


def get_login_email_key(request) -> str:
    """Build a non-PII rate-limit key from FastAPI's already-parsed JSON request body."""
    try:
        payload = json.loads(getattr(request, "_body", b"") or b"{}")
        email = str(payload.get("email", "")).strip().lower()
    except (TypeError, ValueError, AttributeError):
        email = ""
    if not email:
        return f"login-email-invalid:{get_remote_address(request)}"
    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()
    return f"login-email:{digest}"

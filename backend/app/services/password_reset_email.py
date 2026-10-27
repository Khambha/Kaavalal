import os
import smtplib
import ssl
from email.message import EmailMessage


def password_reset_email_configured():
    # This app uses authenticated SMTP (for example, Gmail with an app
    # password). Treat partial settings as unconfigured so the UI doesn't
    # claim that reset email delivery is available when it cannot succeed.
    return all(
        os.getenv(name, "").strip()
        for name in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM_EMAIL")
    )


def send_password_reset_email(recipient: str, reset_url: str):
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM_EMAIL")
    if not password_reset_email_configured():
        return False

    message = EmailMessage()
    message["Subject"] = "Reset your Kaavalal password"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "We received a request to reset your Kaavalal password.\n\n"
        f"Use this link within 30 minutes to choose a new password:\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
    use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() not in {"0", "false", "no"}

    with smtplib.SMTP(host, port, timeout=timeout) as server:
        if use_tls:
            server.starttls(context=ssl.create_default_context())
        server.login(username, password)
        server.send_message(message)
    return True

import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


def password_reset_email_configured():
    # This app uses authenticated SMTP (for example, Gmail with an app
    # password). Treat partial settings as unconfigured so the UI doesn't
    # claim that reset email delivery is available when it cannot succeed.
    return all((settings.SMTP_HOST, settings.SMTP_USERNAME, settings.SMTP_PASSWORD, settings.SMTP_FROM_EMAIL))


def send_password_reset_email(recipient: str, reset_url: str):
    host = settings.SMTP_HOST
    sender = settings.SMTP_FROM_EMAIL
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

    port = settings.SMTP_PORT
    username = settings.SMTP_USERNAME
    password = settings.SMTP_PASSWORD
    timeout = settings.SMTP_TIMEOUT_SECONDS
    use_tls = settings.SMTP_USE_TLS

    with smtplib.SMTP(host, port, timeout=timeout) as server:
        if use_tls:
            server.starttls(context=ssl.create_default_context())
        server.login(username, password)
        server.send_message(message)
    return True

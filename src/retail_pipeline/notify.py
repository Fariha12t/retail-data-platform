"""Failure / data-quality notifications. Never raises: alerting must not break the pipeline."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

import requests

from .config import Settings, get_settings
from .logging_setup import get_logger

log = get_logger(__name__)


def send_alert(title: str, message: str, severity: str = "error", settings: Settings | None = None) -> None:
    s = settings or get_settings()
    log_fn = log.error if severity == "error" else log.warning
    log_fn("ALERT [%s] %s - %s", severity, title, message)
    if s.slack_webhook_url:
        try:
            requests.post(
                s.slack_webhook_url,
                json={"text": f":rotating_light: *{title}* ({severity})\n{message}"},
                timeout=10,
            )
        except Exception as exc:
            log.warning("slack alert failed: %s", exc)
    if s.smtp_host and s.alert_email_to:
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[retail-data-platform] {title}"
            msg["From"] = s.smtp_user or "pipeline@localhost"
            msg["To"] = s.alert_email_to
            msg.set_content(message)
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
                smtp.starttls()
                if s.smtp_user and s.smtp_password:
                    smtp.login(s.smtp_user, s.smtp_password)
                smtp.send_message(msg)
        except Exception as exc:
            log.warning("email alert failed: %s", exc)

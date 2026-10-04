from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from backend.config import settings

logger = logging.getLogger(__name__)

"""Outgoing email over SMTP (Gmail works with smtp.gmail.com:587 + an App Password).

Only two messages exist: the sign-up verification code and a short welcome note.
Nothing here ever logs the SMTP password or the verification code itself."""


class MailError(RuntimeError):
    pass


def enabled() -> bool:
    return settings.smtp_configured


def _sender() -> str:
    return formataddr((settings.smtp_from_name, settings.smtp_from or settings.smtp_user))


def send(to: str, subject: str, text: str, html: str) -> None:
    if not enabled():
        raise MailError("SMTP is not configured")
    message = EmailMessage()
    message["From"] = _sender()
    message["To"] = to
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=(settings.smtp_from or settings.smtp_user).split("@")[-1] or None)
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    security = settings.smtp_security.lower()
    try:
        if security == "ssl":
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=ssl.create_default_context()) as smtp:
                _login_and_send(smtp, message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
                if security == "starttls":
                    smtp.starttls(context=ssl.create_default_context())
                _login_and_send(smtp, message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("sending email to %s failed: %s", to, type(exc).__name__)
        raise MailError(f"could not send email ({type(exc).__name__})") from exc


def _login_and_send(smtp: smtplib.SMTP, message: EmailMessage) -> None:
    if settings.smtp_user and settings.smtp_password:
        smtp.login(settings.smtp_user, settings.smtp_password)
    smtp.send_message(message)


# --- templates ---

_ACCENT = "#b4e768"
_INK = "#0a1010"


def _shell(title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#0d1414;font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#e8efe6">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0d1414;padding:32px 12px">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background:#141d1d;border:1px solid #243030;border-radius:12px">
        <tr><td style="padding:28px 28px 8px 28px">
          <div style="font-weight:800;font-size:16px;letter-spacing:-0.01em">
            <span style="display:inline-block;width:10px;height:10px;background:{_ACCENT};margin-right:8px"></span>IdeaFeed AI
          </div>
          <h1 style="font-size:22px;line-height:1.3;margin:22px 0 8px 0;color:#f4f7f2">{title}</h1>
        </td></tr>
        <tr><td style="padding:0 28px 28px 28px;font-size:14px;line-height:1.6;color:#b9c4bd">{body_html}</td></tr>
      </table>
      <p style="font-size:11px;color:#5d6b66;margin-top:16px">You received this because this address was used on IdeaFeed AI.</p>
    </td></tr>
  </table>
</body></html>"""


def verification_email(code: str, minutes: int) -> tuple[str, str, str]:
    subject = f"{code} is your IdeaFeed AI verification code"
    text = (
        f"Your IdeaFeed AI verification code is {code}\n\n"
        f"Enter it on the sign-up screen to activate your account. It expires in {minutes} minutes.\n"
        "If you didn't try to create an account, you can ignore this email."
    )
    html = _shell(
        "Confirm your email",
        f"""<p style="margin:0 0 18px 0">Enter this code on the sign-up screen to activate your account.</p>
        <div style="font-family:Consolas,Menlo,monospace;font-size:34px;font-weight:700;letter-spacing:10px;
                    background:{_INK};border:1px solid #2c3a3a;border-radius:10px;padding:16px 0;text-align:center;color:{_ACCENT}">{code}</div>
        <p style="margin:18px 0 0 0">It expires in {minutes} minutes. If you didn't try to create an account, you can ignore this email.</p>""",
    )
    return subject, text, html


def welcome_email(signup_credits: int) -> tuple[str, str, str]:
    subject = "Welcome to IdeaFeed AI"
    credit_line = f"{signup_credits} free credits are in your account." if signup_credits > 0 else ""
    text = f"Your email is confirmed and your IdeaFeed AI account is ready. {credit_line}\nType an idea and get a reviewed, ready-to-post video."
    html = _shell(
        "You're all set",
        f"""<p style="margin:0 0 12px 0">Your email is confirmed and your account is ready.</p>
        {f'<p style="margin:0 0 12px 0"><b style="color:{_ACCENT}">{credit_line}</b></p>' if credit_line else ''}
        <p style="margin:0">Type an idea, pick a style, and get a reviewed, ready-to-post vertical video.</p>""",
    )
    return subject, text, html

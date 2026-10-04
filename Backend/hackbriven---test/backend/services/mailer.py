from __future__ import annotations

import logging
import smtplib
import time
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from html import escape
from pathlib import Path

from backend.config import settings
from backend.core import security
from backend.models.schemas import Job

logger = logging.getLogger(__name__)

"""Outgoing email over SMTP (Gmail works with smtp.gmail.com:587 + an App Password).

Messages: the sign-up verification code, a short welcome note, and "your video is ready"
(MP4 attached when small enough, otherwise a signed download link).
Nothing here ever logs the SMTP password or the verification code itself."""


class MailError(RuntimeError):
    pass


def enabled() -> bool:
    return settings.smtp_configured


def _sender() -> str:
    return formataddr((settings.smtp_from_name, settings.smtp_from or settings.smtp_user))


_SEND_ATTEMPTS = 3


def send(
    to: str,
    subject: str,
    text: str,
    html: str,
    attachments: list[tuple[str, str, bytes]] | None = None,
) -> None:
    """`attachments` = [(filename, mime type like "video/mp4", data), ...]."""
    if not enabled():
        raise MailError("SMTP is not configured")
    message = EmailMessage()
    message["From"] = _sender()
    message["To"] = to
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=(settings.smtp_from or settings.smtp_user).split("@")[-1] or None)
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    for filename, mime, data in attachments or []:
        maintype, _, subtype = mime.partition("/")
        message.add_attachment(data, maintype=maintype, subtype=subtype or "octet-stream", filename=filename)

    security = settings.smtp_security.lower()
    # Uploads with attachments need far longer than a plain text mail; flaky networks drop the
    # connection mid-upload, so retry a few times on a fresh connection before giving up.
    timeout = 120 if attachments else 20
    last: Exception | None = None
    for attempt in range(1, _SEND_ATTEMPTS + 1):
        try:
            if security == "ssl":
                with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=timeout, context=ssl.create_default_context()) as smtp:
                    _login_and_send(smtp, message)
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as smtp:
                    if security == "starttls":
                        smtp.starttls(context=ssl.create_default_context())
                    _login_and_send(smtp, message)
            return
        except smtplib.SMTPAuthenticationError as exc:  # wrong credentials: retrying won't help
            last = exc
            break
        except (smtplib.SMTPException, OSError) as exc:
            last = exc
            logger.warning("sending email to %s failed (attempt %s/%s): %s", to, attempt, _SEND_ATTEMPTS, type(exc).__name__)
            if attempt < _SEND_ATTEMPTS:
                time.sleep(2 * attempt)
    logger.warning("sending email to %s failed: %s", to, type(last).__name__)
    raise MailError(f"could not send email ({type(last).__name__})") from last


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


# --- "your video is ready" ---

HANDOFF_FILE = "qoneqt_handoff.txt"


def mask_email(email: str) -> str:
    """k***@gmail.com - enough for the user to recognise, not enough to harvest."""
    local, sep, domain = (email or "").partition("@")
    if not sep:
        return "***"
    return f"{local[:1]}***@{domain}"


def _job_hook(job: Job) -> str:
    if job.script is not None and job.script.hook:
        return job.script.hook
    if job.scene_plan is not None and job.scene_plan.hook:
        return job.scene_plan.hook
    return ""


def _public_link(job_id: str, path: str) -> str | None:
    base = settings.public_api_url.strip().rstrip("/")
    if not base:
        return None
    return f"{base}/jobs/{job_id}/{path}sig={security.media_sig(job_id)}"


def video_ready_email(
    job: Job,
    *,
    attached: bool,
    video_url: str | None,
    handoff_url: str | None,
    handoff_note: str | None,
) -> tuple[str, str, str]:
    topic = (job.topic or "your idea").strip()
    short_topic = topic if len(topic) <= 80 else topic[:77] + "..."
    hook = _job_hook(job)
    subject = f"Your video is ready: {short_topic}"

    if attached:
        video_line = "Your video is attached to this email (MP4)."
    elif video_url:
        video_line = f"Download your video: {video_url}"
    else:
        video_line = "Your video was too large to attach - open IdeaFeed AI to download it."

    text_parts = [f"Your IdeaFeed AI video is ready.\n\nTopic: {topic}"]
    if hook:
        text_parts.append(f"Hook: {hook}")
    text_parts.append(video_line)
    if attached and video_url:
        text_parts.append(f"You can also download it here: {video_url}")
    if handoff_url:
        text_parts.append(f"Manual handoff package: {handoff_url}")
    if handoff_note:
        text_parts.append(f"--- Manual handoff note ---\n{handoff_note}")
    text = "\n\n".join(text_parts)

    def link(url: str, label: str) -> str:
        return (
            f'<a href="{escape(url, quote=True)}" style="display:inline-block;background:{_ACCENT};color:{_INK};'
            f'font-weight:700;text-decoration:none;padding:10px 16px;border-radius:8px;margin:0 8px 8px 0">{label}</a>'
        )

    body = [f'<p style="margin:0 0 12px 0"><b style="color:#f4f7f2">Topic:</b> {escape(topic)}</p>']
    if hook:
        body.append(f'<p style="margin:0 0 12px 0"><b style="color:#f4f7f2">Hook:</b> {escape(hook)}</p>')
    if attached:
        body.append('<p style="margin:0 0 12px 0">Your video is attached to this email (MP4).</p>')
    elif not video_url:
        body.append('<p style="margin:0 0 12px 0">Your video was too large to attach - open IdeaFeed AI to download it.</p>')
    buttons = ""
    if video_url:
        buttons += link(video_url, "Download video")
    if handoff_url:
        buttons += link(handoff_url, "Handoff package")
    if buttons:
        body.append(f'<p style="margin:4px 0 12px 0">{buttons}</p>')
    if handoff_note:
        body.append(
            '<p style="margin:12px 0 6px 0"><b style="color:#f4f7f2">Manual handoff note</b></p>'
            f'<pre style="white-space:pre-wrap;font-family:Consolas,Menlo,monospace;font-size:12px;background:{_INK};'
            f'border:1px solid #2c3a3a;border-radius:8px;padding:12px;color:#cfd8d2;margin:0">{escape(handoff_note)}</pre>'
        )
    html = _shell("Your video is ready", "\n".join(body))
    return subject, text, html


def send_video_email(job: Job, job_dir: Path, to: str | None = None, share_url: str | None = None) -> bool:
    """Email the finished video plus its manual-handoff package to `to` (default: the job's owner).
    Never raises: returns True only if it was sent."""
    recipient = to or job.owner
    try:
        if not recipient:
            logger.info("job=%s video email skipped: no recipient", job.id)
            return False
        if not enabled():
            logger.info("job=%s video email skipped: SMTP is not configured", job.id)
            return False
        video = job_dir / "final.mp4"
        if not video.exists():
            logger.info("job=%s video email skipped: no final video", job.id)
            return False

        max_bytes = int(settings.email_attachment_max_mb * 1024 * 1024)
        # With a share-page link the email stays tiny and sends in seconds; only attach without one.
        attach = not share_url and video.stat().st_size <= max_bytes
        attachments: list[tuple[str, str, bytes]] = []
        if attach:
            attachments.append((f"ideafeed-{job.id}.mp4", "video/mp4", video.read_bytes()))

        handoff_path = job_dir / HANDOFF_FILE
        if not handoff_path.exists():
            try:  # always include the handoff package, even before the job was handed off
                from backend.services import qoneqt_handoff

                qoneqt_handoff.build_handoff(job, job_dir)
            except Exception:  # noqa: BLE001 - the video still goes out without it
                logger.warning("job=%s could not build the handoff note for the email", job.id)
        handoff_note = job.manual_handoff_note
        if not handoff_note and handoff_path.exists():
            handoff_note = handoff_path.read_text(encoding="utf-8", errors="replace")
        handoff_url = _public_link(job.id, "handoff?") if handoff_path.exists() else None
        if handoff_path.exists():
            attachments.append((f"qoneqt_handoff_{job.id}.txt", "text/plain", handoff_path.read_bytes()))

        subject, text, html = video_ready_email(
            job,
            attached=attach,
            video_url=share_url or _public_link(job.id, "video?download=true&"),
            handoff_url=handoff_url,
            handoff_note=handoff_note,
        )
        try:
            send(recipient, subject, text, html, attachments=attachments)
        except MailError:
            if not attach:
                raise
            logger.warning("job=%s video attachment would not upload; sending the email with a link instead", job.id)
            attach = False
            subject, text, html = video_ready_email(
                job,
                attached=False,
                video_url=share_url or _public_link(job.id, "video?download=true&"),
                handoff_url=handoff_url,
                handoff_note=handoff_note,
            )
            send(recipient, subject, text, html, attachments=[a for a in attachments if a[1] != "video/mp4"])
        logger.info("job=%s video email sent to %s (attached=%s)", job.id, mask_email(recipient), attach)
        return True
    except MailError:
        logger.warning("job=%s video email to %s failed", job.id, mask_email(recipient))
        return False
    except Exception:  # noqa: BLE001 - email must never break the caller
        logger.exception("job=%s video email failed unexpectedly", job.id)
        return False

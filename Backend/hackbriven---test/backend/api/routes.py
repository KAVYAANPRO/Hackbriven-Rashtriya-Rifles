from __future__ import annotations

import hmac
import re
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from backend.config import settings
from backend.core import credits, orders, plans, security, users
from backend.core.credits import DEFAULT_ACCOUNT, InsufficientCreditsError
from backend.core.exceptions import InvalidJobStateError, JobNotFoundError
from backend.core.job_manager import JobManager
from backend.core.pipeline import run as run_pipeline
from backend.models.schemas import CaptionSettings, Job, JobStatus, Language, MotionTier, QualityReport
from backend.core.exceptions import PipelineError
from backend.services import content_safety, exporter, mailer, payments, prompt_booster, qoneqt_handoff, styles, uploads
from backend.services import captions as captions_service, video_composer
from backend.services.payments import PaymentError, SignatureVerificationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])
credits_router = APIRouter(prefix="/credits", tags=["credits"])
meta_router = APIRouter(tags=["meta"])
auth_router = APIRouter(prefix="/auth", tags=["auth"])
uploads_router = APIRouter(prefix="/uploads", tags=["uploads"])
prompt_router = APIRouter(prefix="/prompt", tags=["prompt"])
job_manager = JobManager()


# --------------------------------------------------------------------------
# Identity
#
# Who is calling? Three kinds of caller are supported:
#   * a signed-in user  - "Authorization: Bearer <session token>"  -> their email
#   * a legacy service  - "Authorization: Bearer <BACKEND_API_KEY>" -> DEFAULT_ACCOUNT
#   * anonymous         - no header                                  -> DEFAULT_ACCOUNT
# Anonymous/legacy callers are refused on mutating endpoints once
# BACKEND_API_KEY is set, and on everything user-scoped once REQUIRE_LOGIN is on.
# --------------------------------------------------------------------------


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def _is_legacy_key(token: str) -> bool:
    if not settings.has_auth:
        return False
    try:
        return hmac.compare_digest(token, settings.backend_api_key)
    except TypeError:  # non-ASCII text can't be compared safely
        return False


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="missing or invalid Authorization header")


def _resolve_account(authorization: str | None, *, mutating: bool) -> str:
    token = _bearer(authorization)
    if token:
        email = security.verify_token(token)
        if email:
            return email
        if _is_legacy_key(token):
            return DEFAULT_ACCOUNT
        raise _unauthorized()
    if settings.require_login or (mutating and settings.has_auth):
        raise _unauthorized()
    return DEFAULT_ACCOUNT


def account_required(authorization: str | None = Header(default=None)) -> str:
    """For endpoints that change something."""
    return _resolve_account(authorization, mutating=True)


def account_optional(authorization: str | None = Header(default=None)) -> str:
    """For read endpoints (still scoped to whoever is asking)."""
    return _resolve_account(authorization, mutating=False)


def require_auth(authorization: str | None = Header(default=None)) -> None:
    """Kept for callers that only need the gate, not the identity."""
    _resolve_account(authorization, mutating=True)


def _owner_of(account: str) -> str | None:
    return None if account == DEFAULT_ACCOUNT else account


def _owns(job: Job, account: str) -> bool:
    return job.owner == _owner_of(account)


def _get_owned_job(job_id: str, account: str) -> Job:
    try:
        job = job_manager.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not _owns(job, account):
        # Same answer as "doesn't exist" so job ids can't be probed across accounts.
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    return job


# --------------------------------------------------------------------------
# Job view: the stored job plus what a browser needs to render media
# --------------------------------------------------------------------------


class JobView(Job):
    media_sig: str = ""  # appended as ?sig= to video/scene/handoff URLs (tags can't send headers)
    ready_scene_images: list[int] = Field(default_factory=list)  # scene indices whose image already exists
    has_video: bool = False


def _job_dir(job_id: str) -> Path:
    return settings.storage_path / job_id


def _view(job: Job) -> JobView:
    job_dir = _job_dir(job.id)
    ready: list[int] = []
    if job.scene_plan is not None:
        ready = [s.index for s in job.scene_plan.scenes if (job_dir / f"scene_{s.index:02d}.png").exists()]
    has_video = bool(job.result_path) and (job_dir / "final.mp4").exists()
    return JobView(**job.model_dump(), media_sig=security.media_sig(job.id), ready_scene_images=ready, has_video=has_video)


def _is_admin(email: str) -> bool:
    return users.normalize_email(email) in settings.admin_email_list


def require_admin(account: str = Depends(account_required)) -> str:
    """Master-admin only (ADMIN_EMAILS). Anyone else - signed in or not - gets 403."""
    user = users.get(account) if account != DEFAULT_ACCOUNT else None
    if user is None or not users.is_verified(user) or not _is_admin(account):
        raise HTTPException(status_code=403, detail="admin access only")
    return account


def _user_view(user: dict) -> dict:
    plan_id = users.effective_plan(user)
    return {
        "email": user["email"],
        "plan": plan_id,
        "plan_expires_at": user.get("plan_expires_at") if plan_id != plans.FREE_PLAN_ID else None,
        "balance": credits.get_balance(user["email"]),
        "created_at": user["created_at"],
        "email_verified": users.is_verified(user),
        "is_admin": _is_admin(user["email"]),
    }


# --------------------------------------------------------------------------
# Auth / accounts
# --------------------------------------------------------------------------


class LoginRequest(BaseModel):
    # Legacy shared-secret login (the Gradio UI): only api_key is sent.
    api_key: str = ""
    # Account login: email + password.
    email: str | None = None
    password: str | None = None


class RegisterRequest(BaseModel):
    email: str
    password: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


class ResendCodeRequest(BaseModel):
    email: str


def _grant_signup_credits(email: str) -> None:
    if settings.signup_credits > 0:
        try:
            credits.add_credits(settings.signup_credits, reason="signup_bonus", account=email)
        except Exception:  # noqa: BLE001 - the account exists; don't fail sign-up over the bonus
            logger.exception("could not grant signup credits to %s", email)


def _send_code(email: str) -> None:
    code = users.start_verification(email, settings.verification_code_ttl_minutes)
    subject, text, html = mailer.verification_email(code, settings.verification_code_ttl_minutes)
    mailer.send(email, subject, text, html)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@auth_router.post("/register")
def register(body: RegisterRequest, request: Request) -> dict:
    if security.rate_limited(f"register:{_client_key(request)}", limit=20, window_seconds=600):
        raise HTTPException(status_code=429, detail="too many sign-up attempts, try again later")
    verify = settings.email_verification_enabled
    try:
        user = users.register(body.email, body.password, verified=not verify)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except users.UserExistsError as exc:
        existing = users.get(body.email)
        if verify and existing is not None and not users.is_verified(existing):
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "this email is waiting for verification - enter the code we sent, or request a new one",
                    "verification_required": True,
                    "email": existing["email"],
                },
            ) from exc
        raise HTTPException(status_code=409, detail="an account with this email already exists") from exc

    if not verify:
        _grant_signup_credits(user["email"])
        return {"token": security.issue_token(user["email"]), "user": _user_view(user)}

    # Verification on: no session and no credits until the emailed code is confirmed.
    try:
        _send_code(user["email"])
    except mailer.MailError as exc:
        users.delete(user["email"])  # let them try again instead of being stuck with an unconfirmable account
        raise HTTPException(status_code=503, detail="we couldn't send the verification email - try again in a minute") from exc
    return {
        "verification_required": True,
        "email": user["email"],
        "expires_in_minutes": settings.verification_code_ttl_minutes,
    }


@auth_router.post("/verify-email")
def verify_email(body: VerifyEmailRequest, request: Request) -> dict:
    email = users.normalize_email(body.email)
    if security.rate_limited(f"verify-ip:{_client_key(request)}", limit=30, window_seconds=600):
        raise HTTPException(status_code=429, detail="too many attempts, try again later")
    try:
        user = users.confirm_code(email, body.code)
    except users.VerificationError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    _grant_signup_credits(user["email"])
    try:
        subject, text, html = mailer.welcome_email(settings.signup_credits)
        mailer.send(user["email"], subject, text, html)
    except mailer.MailError:
        logger.warning("welcome email to %s not sent", user["email"])  # verification already succeeded
    return {"token": security.issue_token(user["email"]), "user": _user_view(user)}


@auth_router.post("/resend-code")
def resend_code(body: ResendCodeRequest, request: Request) -> dict:
    email = users.normalize_email(body.email)
    if security.rate_limited(f"resend:{email}", limit=1, window_seconds=45) or security.rate_limited(
        f"resend-hour:{email}", limit=6, window_seconds=3600
    ):
        raise HTTPException(status_code=429, detail="please wait a moment before asking for another code")
    user = users.get(email)
    if user is None or users.is_verified(user):
        # Same answer either way, so this can't be used to discover which emails have accounts.
        return {"sent": True, "expires_in_minutes": settings.verification_code_ttl_minutes}
    try:
        _send_code(email)
    except mailer.MailError as exc:
        raise HTTPException(status_code=503, detail="we couldn't send the email - try again in a minute") from exc
    return {"sent": True, "expires_in_minutes": settings.verification_code_ttl_minutes}


@auth_router.post("/login")
def login(body: LoginRequest, request: Request) -> dict:
    """Two modes. {email, password} signs a user in and returns a session
    token + profile. {api_key} is the original shared-secret check (it
    doesn't issue a session; the caller resends the key as the bearer token)."""
    if body.email is not None:
        email = users.normalize_email(body.email)
        if security.rate_limited(f"login:{email}", limit=10, window_seconds=600) or security.rate_limited(
            f"login-ip:{_client_key(request)}", limit=60, window_seconds=600
        ):
            raise HTTPException(status_code=429, detail="too many sign-in attempts, try again later")
        user = users.authenticate(email, body.password or "")
        if user is None:
            raise HTTPException(status_code=401, detail="invalid email or password")
        if not users.is_verified(user):
            raise HTTPException(
                status_code=403,
                detail={"message": "confirm your email first - enter the code we sent you", "verification_required": True, "email": user["email"]},
            )
        return {
            "authenticated": True,
            "auth_required": bool(settings.has_auth or settings.require_login),
            "token": security.issue_token(user["email"]),
            "user": _user_view(user),
        }

    if not settings.has_auth:
        return {"authenticated": True, "auth_required": False}
    if body.api_key == settings.backend_api_key:
        return {"authenticated": True, "auth_required": True}
    raise HTTPException(status_code=401, detail="invalid API key")


class ClerkLoginRequest(BaseModel):
    token: str = Field(..., max_length=8192)


@auth_router.post("/clerk")
def clerk_login(body: ClerkLoginRequest, request: Request) -> dict:
    """Exchange a Clerk session token ("Continue with Google") for this app's own session.
    The Clerk-verified email is the account key: a new account is created (already verified,
    with the signup bonus) or the existing one is signed in. Same response shape as /auth/login."""
    if not settings.has_clerk:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this server")
    if security.rate_limited(f"clerk-ip:{_client_key(request)}", limit=60, window_seconds=600):
        raise HTTPException(status_code=429, detail="too many sign-in attempts, try again later")
    try:
        from backend.services import clerk_auth
    except ImportError as exc:  # PyJWT[crypto] not installed
        logger.error("Clerk sign-in unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Google sign-in is not available on this server") from exc
    try:
        email = clerk_auth.verified_email(body.token)
    except clerk_auth.ClerkError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    try:
        user, activated = users.ensure_external(email, "clerk")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except users.UserExistsError as exc:
        raise HTTPException(status_code=409, detail="could not create your account - try again") from exc
    if activated:
        _grant_signup_credits(user["email"])
    return {
        "authenticated": True,
        "auth_required": bool(settings.has_auth or settings.require_login),
        "token": security.issue_token(user["email"]),
        "user": _user_view(user),
    }


@auth_router.get("/me")
def me(account: str = Depends(account_optional)) -> dict:
    user = users.get(account) if account != DEFAULT_ACCOUNT else None
    if user is None:
        raise _unauthorized()
    return _user_view(user)


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------


class CreateJobRequest(BaseModel):
    topic: str
    motion_tier: MotionTier = MotionTier.BALANCED
    language: Language = Language.EN
    reference_images: list[str] = Field(default_factory=list)
    style: str = "auto"
    style_prompt: str | None = None
    resolution: str = plans.DEFAULT_RESOLUTION
    captions: CaptionSettings = Field(default_factory=CaptionSettings)


_MAX_TOPIC_CHARS = 4000


def _reject_unsafe(*texts: str | None) -> None:
    """422 'Not appropriate video' for 18+, deepfake, gore etc. Runs before any credit is charged."""
    combined = " . ".join(t.strip() for t in texts if t and t.strip())
    verdict = content_safety.review(combined)
    if not verdict.allowed:
        raise HTTPException(
            status_code=422,
            detail={"message": verdict.message, "code": "content_blocked", "category": verdict.category},
        )


@router.post("", response_model=JobView)
def create_job(
    request: CreateJobRequest,
    background_tasks: BackgroundTasks,
    account: str = Depends(account_required),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobView:
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="topic must not be empty")
    if len(topic) > _MAX_TOPIC_CHARS:
        raise HTTPException(status_code=422, detail=f"topic is too long (max {_MAX_TOPIC_CHARS} characters)")

    _reject_unsafe(topic, request.style_prompt if request.style == "custom" else None)

    # Keys are namespaced by account so one caller's key can never hand back another's job.
    scoped_key = f"{account}:{idempotency_key}" if idempotency_key else None
    if scoped_key:
        existing = job_manager.find_by_idempotency_key(scoped_key)
        if existing is not None:
            # Same key already created a job - return it as-is, do not
            # charge credits or start a second pipeline run (PRD 6.6).
            return _view(existing)

    if not styles.is_valid(request.style):
        raise HTTPException(status_code=422, detail=f"unknown style: {request.style!r}")
    style_text = styles.clean_custom(request.style_prompt) if request.style == "custom" else None
    if request.style == "custom" and not style_text:
        raise HTTPException(status_code=422, detail="describe your custom style")
    resolution = plans.resolution_def(request.resolution)
    if resolution is None:
        raise HTTPException(status_code=422, detail=f"unknown resolution: {request.resolution!r}")

    if account != DEFAULT_ACCOUNT:
        user = users.get(account)
        if user is None:
            raise HTTPException(status_code=401, detail="account not found - sign in again")
        plan_id = users.effective_plan(user)
        if not plans.can_use_resolution(plan_id, resolution.id):
            needed = plans.cheapest_plan_for_resolution(resolution.id)
            current = plans.plan_def(plan_id)
            raise HTTPException(
                status_code=403,
                detail={
                    "message": f"The {current.name} plan can't deliver {resolution.label}. Upgrade to {needed.name} to unlock it.",
                    "required_plan": needed.id,
                    "plan": plan_id,
                },
            )
        if not plans.can_use(plan_id, request.motion_tier):
            needed = plans.cheapest_plan_for(request.motion_tier)
            current = plans.plan_def(plan_id)
            raise HTTPException(
                status_code=403,
                detail={
                    "message": (
                        f"The {current.name} plan can't use the {request.motion_tier.value} tier. "
                        f"Upgrade to {needed.name} to unlock it."
                    ),
                    "required_plan": needed.id,
                    "plan": plan_id,
                },
            )

    if request.reference_images:
        if len(request.reference_images) > settings.max_upload_images:
            raise HTTPException(status_code=422, detail=f"at most {settings.max_upload_images} reference images")
        try:
            uploads.resolve(request.reference_images, account)
        except uploads.UploadError as exc:
            raise HTTPException(status_code=exc.status, detail=str(exc)) from exc

    try:
        credits.charge(
            request.motion_tier,
            reason=f"job:{request.motion_tier.value}",
            account=account,
            surcharge=resolution.credit_surcharge,
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=402,
            detail={
                "message": str(exc),
                "required": exc.required,
                "available": exc.available,
                "top_up": "/credits/create-order",
            },
        ) from exc

    job = job_manager.create(
        topic,
        motion_tier=request.motion_tier,
        language=request.language,
        idempotency_key=scoped_key,
        owner=_owner_of(account),
        reference_images=request.reference_images,
        style=request.style,
        style_prompt=style_text,
        resolution=resolution.id,
        captions=request.captions,
    )
    background_tasks.add_task(run_pipeline, job.id, job_manager)
    return _view(job)


@router.get("", response_model=list[JobView])
def list_jobs(account: str = Depends(account_optional)) -> list[JobView]:
    mine = [job for job in job_manager.list() if _owns(job, account)]
    mine.sort(key=lambda job: job.created_at, reverse=True)
    return [_view(job) for job in mine]


@router.get("/{job_id}", response_model=JobView)
def get_job(job_id: str, account: str = Depends(account_optional)) -> JobView:
    return _view(_get_owned_job(job_id, account))


@router.get("/{job_id}/result")
def get_job_result(job_id: str, account: str = Depends(account_optional)) -> dict:
    job = _get_owned_job(job_id, account)

    if not job.result_path:
        raise HTTPException(status_code=409, detail="job has no result yet")

    return {"job_id": job_id, "result_path": job.result_path, "status": job.status}


@router.get("/{job_id}/quality-report", response_model=QualityReport)
def get_job_quality_report(job_id: str, account: str = Depends(account_optional)) -> QualityReport:
    job = _get_owned_job(job_id, account)

    if job.quality_report is None:
        raise HTTPException(status_code=409, detail="quality report not available yet")

    return job.quality_report


# --- media: authorised by the job's signature (for <video>/<img>) or by the caller's own login ---


def _media_job(job_id: str, sig: str | None, authorization: str | None) -> Job:
    try:
        job = job_manager.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if security.verify_media_sig(job_id, sig):
        return job
    return _get_owned_job(job_id, _resolve_account(authorization, mutating=False))


@router.get("/{job_id}/video")
def get_job_video(
    job_id: str,
    sig: str | None = Query(default=None),
    download: bool = Query(default=False),
    authorization: str | None = Header(default=None),
) -> FileResponse:
    job = _media_job(job_id, sig, authorization)
    path = _job_dir(job.id) / "final.mp4"
    if not job.result_path or not path.exists():
        raise HTTPException(status_code=409, detail="job has no video yet")
    # FileResponse serves HTTP Range requests, which browsers need for seeking.
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"ideafeed-{job.id}.mp4",
        content_disposition_type="attachment" if download else "inline",
    )


@router.get("/{job_id}/scenes/{index}/image")
def get_scene_image(
    job_id: str,
    index: int,
    sig: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> FileResponse:
    job = _media_job(job_id, sig, authorization)
    path = _job_dir(job.id) / f"scene_{index:02d}.png"
    if index < 0 or not path.exists():
        raise HTTPException(status_code=404, detail="scene image not generated yet")
    return FileResponse(path, media_type="image/png")


@router.get("/{job_id}/handoff")
def get_handoff(
    job_id: str,
    sig: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> FileResponse:
    job = _media_job(job_id, sig, authorization)
    path = _job_dir(job.id) / "qoneqt_handoff.txt"
    if not path.exists():
        raise HTTPException(status_code=409, detail="no handoff package yet - publish the job first")
    return FileResponse(
        path,
        media_type="text/plain; charset=utf-8",
        filename=f"qoneqt_handoff_{job.id}.txt",
        content_disposition_type="attachment",
    )


@router.get("/{job_id}/download")
def download_job_video(
    job_id: str,
    format: str = Query(default="mp4"),
    sig: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> FileResponse:
    """The finished video in another container/codec (MP4, MOV, WebM, MKV, GIF, MP3). Converted
    on the first request and cached, so repeat downloads are instant."""
    job = _media_job(job_id, sig, authorization)
    fmt = exporter.get_format(format)
    if fmt is None:
        raise HTTPException(status_code=422, detail=f"unknown format: {format!r}")
    job_dir = _job_dir(job.id)
    if not job.result_path or not (job_dir / "final.mp4").exists():
        raise HTTPException(status_code=409, detail="job has no video yet")
    try:
        path = exporter.export_format(job_dir, fmt.id)
    except PipelineError as exc:
        raise HTTPException(status_code=500, detail=f"could not convert to {fmt.label}: {exc.reason}") from exc
    return FileResponse(
        path,
        media_type=fmt.mime,
        filename=f"ideafeed-{job.id}.{fmt.ext}",
        content_disposition_type="attachment",
    )


# --- lifecycle ---


class ApproveRequest(BaseModel):
    approver: str = "unknown"


def _email_video_task(job_id: str, to: str | None = None, share_url: str | None = None) -> None:
    """Runs after the response is sent; mailer.send_video_email never raises."""
    try:
        job = job_manager.get(job_id)
    except JobNotFoundError:
        return
    mailer.send_video_email(job, _job_dir(job_id), to=to, share_url=share_url)


class EmailVideoRequest(BaseModel):
    to: str | None = Field(default=None, max_length=254)
    share_url: str | None = Field(default=None, max_length=1000)


def _queue_video_email(background_tasks: BackgroundTasks, job: Job) -> None:
    """Auto-send after approve / manual handoff. Silently skipped for anonymous jobs or when SMTP is off."""
    if job.owner and mailer.enabled():
        background_tasks.add_task(_email_video_task, job.id)


@router.post("/{job_id}/approve", response_model=JobView)
def approve_job(
    job_id: str,
    request: ApproveRequest,
    background_tasks: BackgroundTasks,
    account: str = Depends(account_required),
) -> JobView:
    _get_owned_job(job_id, account)
    try:
        job = job_manager.approve(job_id, approver=request.approver)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidJobStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _queue_video_email(background_tasks, job)
    return _view(job)


@router.post("/{job_id}/email")
def email_job_video(
    job_id: str,
    background_tasks: BackgroundTasks,
    request: EmailVideoRequest | None = None,
    account: str = Depends(account_required),
) -> dict:
    """Send the finished video and its manual-handoff package by email: to `to` when given
    (share with anyone), otherwise to the job owner's account email."""
    job = _get_owned_job(job_id, account)
    to = (request.to or "").strip() if request else ""
    if to and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", to):
        raise HTTPException(status_code=422, detail="enter a valid email address")
    to = to or job.owner or ""
    if not to:
        raise HTTPException(status_code=409, detail="enter an email address to send this video to")
    if not job.result_path or not (_job_dir(job_id) / "final.mp4").exists():
        raise HTTPException(status_code=409, detail="the video isn't finished yet")
    if not mailer.enabled():
        raise HTTPException(status_code=503, detail="email isn't set up on this server")
    if security.rate_limited(f"email-video:{job_id}:{to.lower()}", limit=1, window_seconds=60):
        raise HTTPException(status_code=429, detail="this video was just emailed there - try again in a minute")
    if security.rate_limited(f"email-video-account:{account}", limit=20, window_seconds=3600):
        raise HTTPException(status_code=429, detail="too many emails sent - try again later")
    share = (request.share_url or "").strip() if request else ""
    # Only our own watch-page link for this job, signed for this job - never an arbitrary URL.
    if not (share.startswith(("http://", "https://")) and f"#/watch/{job_id}?" in share and security.media_sig(job_id) in share):
        share = ""
    background_tasks.add_task(_email_video_task, job_id, to, share or None)
    return {"queued": True, "to": mailer.mask_email(to)}


@router.post("/{job_id}/captions", response_model=JobView)
def restyle_captions(job_id: str, request: CaptionSettings, account: str = Depends(account_required)) -> JobView:
    """Re-burn a finished video's captions with new settings (on/off, size, colours, language).
    Reuses the rendered scenes and narration, so only the caption and audio-mux steps run."""
    job = _get_owned_job(job_id, account)
    job_dir = _job_dir(job_id)
    silent, narration = job_dir / "silent.mp4", job_dir / "narration.wav"
    if not job.result_path or not (job_dir / "final.mp4").exists():
        raise HTTPException(status_code=409, detail="the video isn't finished yet")
    if not (silent.exists() and narration.exists() and (job_dir / captions_service.SOURCE_FILE).exists()):
        raise HTTPException(
            status_code=409, detail="this video was made before caption editing was available - generate it again"
        )
    with exporter._lock_for(f"{job_id}:captions"):
        try:
            scenes = captions_service.display_scenes(captions_service.load_source(job_dir), request, job.language)
            music = job_dir / "music.wav"
            final = video_composer.finish_video(
                job_dir, silent, narration, scenes, request, music if music.exists() else None
            )
            exporter.deliver_at_resolution(job_dir, final, job.resolution)
        except PipelineError as exc:
            raise HTTPException(status_code=500, detail=f"{exc.stage}: {exc.reason}") from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("job=%s caption restyle failed", job_id)
            raise HTTPException(status_code=500, detail="could not update the captions") from exc
    return _view(job_manager.update(job_id, captions=request))


@router.post("/{job_id}/cancel", response_model=JobView)
def cancel_job(job_id: str, account: str = Depends(account_required)) -> JobView:
    _get_owned_job(job_id, account)
    try:
        return _view(job_manager.cancel(job_id))
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidJobStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{job_id}/publish", response_model=JobView)
def publish_job(job_id: str, background_tasks: BackgroundTasks, account: str = Depends(account_required)) -> JobView:
    """Qoneqt has no public creator-publishing API (confirmed from the
    client's own creator roster spreadsheet), so this always performs the
    honest manual handoff described in qoneqt_handoff.py and sets status to
    MANUAL_HANDOFF - never PUBLISHED, per PRD 6.7: "do not claim successful
    publishing until the platform confirms success."

    Legal from APPROVED, and from PUBLISH_FAILED as a retry. Repeating it on
    a job that already has its handoff just returns the job (no second package).
    """
    job = _get_owned_job(job_id, account)

    if job.status == JobStatus.MANUAL_HANDOFF:
        return _view(job)

    if job.status not in (JobStatus.APPROVED, JobStatus.PUBLISH_FAILED):
        raise HTTPException(
            status_code=409,
            detail=f"job {job_id} must be approved before publishing (current status: {job.status.value})",
        )

    job_dir = settings.storage_path / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        note_path, note_text = qoneqt_handoff.build_handoff(job, job_dir)
    except Exception as exc:  # noqa: BLE001 - surface as a publish failure, not a 500
        return _view(
            job_manager.update(
                job_id,
                status=JobStatus.PUBLISH_FAILED,
                publish_error=str(exc),
            )
        )

    job = job_manager.update(
        job_id,
        status=JobStatus.MANUAL_HANDOFF,
        publish_error=None,
        manual_handoff_path=str(note_path),
        manual_handoff_note=note_text,
    )
    _queue_video_email(background_tasks, job)
    return _view(job)


# --------------------------------------------------------------------------
# Reference-image uploads and prompt boost
# --------------------------------------------------------------------------


@uploads_router.post("")
def upload_images(files: list[UploadFile] = File(...), account: str = Depends(account_required)) -> dict:
    if len(files) > settings.max_upload_images:
        raise HTTPException(status_code=422, detail=f"at most {settings.max_upload_images} images per upload")
    saved: list[dict] = []
    try:
        for file in files:
            # Read one byte past the limit so an oversize file is detected without loading all of it.
            data = file.file.read(settings.max_upload_bytes + 1)
            saved.append(uploads.save_image(account, file.filename or "image", data))
    except uploads.UploadError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    return {"files": saved}


class BoostRequest(BaseModel):
    prompt: str
    language: Language | None = None
    style: str = "auto"
    style_prompt: str | None = None


@prompt_router.post("/boost")
def boost_prompt(body: BoostRequest, account: str = Depends(account_required)) -> dict:
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="write an idea first")
    if len(prompt) > _MAX_TOPIC_CHARS:
        raise HTTPException(status_code=422, detail=f"prompt is too long (max {_MAX_TOPIC_CHARS} characters)")
    if security.rate_limited(f"boost:{account}", limit=30, window_seconds=600):
        raise HTTPException(status_code=429, detail="too many boosts, try again in a few minutes")
    if not styles.is_valid(body.style):
        raise HTTPException(status_code=422, detail=f"unknown style: {body.style!r}")
    rules = content_safety.check_rules(prompt)
    if not rules.allowed:
        raise HTTPException(
            status_code=422,
            detail={"message": rules.message, "code": "content_blocked", "category": rules.category},
        )
    text, source = prompt_booster.boost(
        prompt, body.language, body.style, styles.clean_custom(body.style_prompt) or None
    )
    return {"text": text, "source": source}


# --------------------------------------------------------------------------
# Plans, credits and payments
# --------------------------------------------------------------------------


def _cost_by_tier() -> dict[str, int]:
    return {t.value: credits.cost_for_tier(t) for t in MotionTier}


@meta_router.get("/plans")
def get_plans() -> dict:
    """Public pricing: what the frontend renders instead of hard-coding it."""
    plan_list = [p.to_dict() for p in plans.PLANS]
    for entry in plan_list:
        if entry["id"] == plans.FREE_PLAN_ID:
            entry["credits"] = settings.signup_credits  # the Free plan's credits are the one-time signup grant
    return {
        "cost_by_tier": _cost_by_tier(),
        "plans": plan_list,
        "packs": list(plans.PACKS),
        "signup_credits": settings.signup_credits,
        "styles": [s.to_dict() for s in styles.STYLES],
        "resolutions": [r.to_dict() for r in plans.RESOLUTIONS],
        "formats": [f.to_dict() for f in exporter.FORMATS],
        "payments": {"razorpay_configured": settings.has_razorpay},
    }


@credits_router.get("")
def get_credits(account: str = Depends(account_optional)) -> dict:
    body: dict = {"balance": credits.get_balance(account), "cost_by_tier": _cost_by_tier(), "packs": list(plans.PACKS)}
    user = users.get(account) if account != DEFAULT_ACCOUNT else None
    if user is None:
        body.update(
            plan=None,
            plan_expires_at=None,
            tiers_allowed=[t.value for t in MotionTier],
            resolutions_allowed=[r.id for r in plans.RESOLUTIONS],
        )
    else:
        plan_id = users.effective_plan(user)
        body.update(
            plan=plan_id,
            plan_expires_at=user.get("plan_expires_at") if plan_id != plans.FREE_PLAN_ID else None,
            tiers_allowed=plans.tiers_for(plan_id),
            resolutions_allowed=plans.resolutions_for(plan_id),
        )
    return body


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class CreateOrderRequest(BaseModel):
    pack: int | None = None  # id from GET /plans -> packs
    plan: str | None = None  # "pro" | "studio"


@credits_router.post("/create-order")
def create_order(request: CreateOrderRequest | None = None, account: str = Depends(account_required)) -> dict:
    request = request or CreateOrderRequest()
    if request.plan and request.pack is not None:
        raise HTTPException(status_code=422, detail="choose either a pack or a plan, not both")

    plan_id: str | None = None
    if request.plan:
        plan = plans.plan_def(request.plan)
        if plan is None or plan.price_paise <= 0:
            raise HTTPException(status_code=422, detail=f"{request.plan!r} is not a purchasable plan")
        if account == DEFAULT_ACCOUNT:
            raise HTTPException(status_code=401, detail="sign in to buy a plan")
        kind, amount, grant, plan_id = "plan", plan.price_paise, plan.credits, plan.id
    elif request.pack is not None:
        pack = plans.pack_def(request.pack)
        if pack is None:
            raise HTTPException(status_code=422, detail=f"unknown credit pack: {request.pack}")
        kind, amount, grant = "pack", pack["price_paise"], pack["credits"]
    else:
        kind, amount, grant = "legacy", settings.razorpay_package_amount_paise, settings.razorpay_package_credits

    try:
        order = payments.create_order(
            receipt=f"{kind}_{uuid.uuid4().hex[:12]}",
            amount_paise=amount,
            credits=grant,
            notes={"kind": kind, **({"plan": plan_id} if plan_id else {})},
        )
    except PaymentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    orders.create_pending(
        order["order_id"], account=account, kind=kind, credits=grant, amount_paise=amount, plan=plan_id
    )
    return {**order, "kind": kind, **({"plan": plan_id} if plan_id else {})}


@credits_router.post("/verify-payment")
def verify_payment(request: VerifyPaymentRequest, account: str = Depends(account_required)) -> dict:
    try:
        payments.verify_payment_signature(
            order_id=request.razorpay_order_id,
            payment_id=request.razorpay_payment_id,
            signature=request.razorpay_signature,
        )
    except SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PaymentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # The signature only proves the payment is genuine. What was bought, and
    # by whom, comes from the order we recorded when it was created - and it
    # can be redeemed exactly once, so replaying a captured signature is harmless.
    order = orders.get(request.razorpay_order_id)
    if order is None or order["account"] != account:
        raise HTTPException(status_code=404, detail="unknown order")

    user = users.get(account) if account != DEFAULT_ACCOUNT else None

    def _state(added: int, already: bool, balance: int | None = None) -> dict:
        plan_id = users.effective_plan(user) if user else None
        return {
            "balance": credits.get_balance(account) if balance is None else balance,
            "plan": plan_id,
            "plan_expires_at": (user or {}).get("plan_expires_at") if plan_id not in (None, plans.FREE_PLAN_ID) else None,
            "credits_added": added,
            "already_processed": already,
        }

    if orders.claim_paid(order["order_id"], request.razorpay_payment_id) is None:
        return _state(0, True)

    try:
        new_balance = credits.add_credits(
            order["credits"], reason=f"razorpay:{request.razorpay_payment_id}", account=account
        )
    except Exception as exc:  # noqa: BLE001
        orders.release(order["order_id"])  # nothing was granted - let the buyer retry
        logger.exception("granting credits for order %s failed", order["order_id"])
        raise HTTPException(status_code=500, detail="payment verified but credits could not be added; retry") from exc

    if order["kind"] == "plan" and order.get("plan"):
        try:
            user = users.activate_plan(account, order["plan"]) or user
        except Exception as exc:  # noqa: BLE001
            # Credits are already granted, so don't release the order (a retry would double-credit).
            logger.exception("activating plan for order %s failed", order["order_id"])
            raise HTTPException(
                status_code=500, detail="credits were added but the plan could not be activated; contact support"
            ) from exc

    return _state(order["credits"], False, new_balance)


# --------------------------------------------------------------------------
# Meta / observability
# --------------------------------------------------------------------------


def _image_chain_status() -> dict:
    """The image chain exactly as generate_image() builds it: only the providers allowed by
    IMAGE_PROVIDERS, in that order, then the local title card."""
    ids = {"cloudflare": "cloudflare", "openrouter": "openrouter", "nvidia": "nvidia_sd35", "pollinations": "pollinations"}
    configured = {
        "cloudflare": settings.has_cloudflare,
        "openrouter": bool(settings.openrouter_api_key and settings.openrouter_image_model_list),
        "nvidia_sd35": bool(settings.nvidia_api_key),
        "pollinations": bool(settings.image_use_pollinations),
    }
    chain = [ids[name] for name in settings.image_provider_list if name in ids]
    from backend.services import image_generator

    until = image_generator.cloudflare_quota_exhausted_until() if "cloudflare" in chain else None
    return {
        "chain": [*chain, "local_placeholder"],
        "configured": {**{name: configured[name] for name in chain}, "local_placeholder": True},
        # Set when today's free Cloudflare allowance is used up (UTC ISO time it comes back).
        "quota_exhausted_until": until.isoformat() if until else None,
    }


@meta_router.get("/providers/status")
def providers_status() -> dict:
    """Public: what the app needs (which stages work, auth/payments/email flags). Operational detail
    like key-pool sizes and per-account image quota is only in GET /admin/providers."""
    full = _full_provider_status()
    full["motion"] = {k: v for k, v in full["motion"].items() if k != "key_pool_size"}
    return full


@meta_router.get("/admin/providers")
def admin_providers(_admin: str = Depends(require_admin)) -> dict:
    """The "AI orchestra" view for the master admin: every chain, key-pool sizes and the state of each
    Cloudflare image account."""
    from backend.services import image_generator

    full = _full_provider_status()
    full["image"]["cloudflare_accounts"] = image_generator.cloudflare_account_status()
    return full


def _full_provider_status() -> dict:
    """Which providers are configured per pipeline stage, without exposing
    any secret values (PRD 6.9 + 8: 'configured provider capabilities
    without exposing secrets'). This is also the "AI orchestra" view: each
    stage lists its fallback chain in the exact order call_with_fallback
    tries them, so it's visible that losing one provider doesn't stop the
    pipeline. Chain names match the provider names recorded in a job's
    provider_events."""
    return {
        "script": {
            "chain": ["gemini", "groq", "openrouter", "local_template"],
            "configured": {
                "gemini": bool(settings.gemini_key_pool),
                "groq": bool(settings.groq_key_pool),
                "openrouter": bool(settings.openrouter_key_pool),
                "local_template": True,
            },
        },
        "image": _image_chain_status(),
        "voice": {
            "chain": ["edge-tts", "gtts"],
            "configured": {"edge-tts": True, "gtts": True},
        },
        "captions": {
            "chain": ["groq_whisper", "local_whisper"],
            "configured": {
                "groq_whisper": bool(settings.groq_api_key),
                "local_whisper": True,
            },
        },
        "motion": {
            "chain": ["eightscale", "magic_hour", "ken_burns"],
            "configured": {
                "eightscale": bool(settings.eightscale_key_pool),
                "magic_hour": bool(settings.magic_hour_key_pool),
                "ken_burns": True,
            },
            "key_pool_size": {
                "eightscale": len(settings.eightscale_key_pool),
                "magic_hour": len(settings.magic_hour_key_pool),
            },
        },
        "payments": {"razorpay_configured": settings.has_razorpay},
        "persistence": {"mongodb_configured": bool(settings.mongodb_uri)},
        "auth": {"enabled": settings.has_auth},
        "accounts": {
            "enabled": True,
            "login_required": bool(settings.require_login),
            "email_verification": settings.email_verification_enabled,
        },
        "email": {"smtp_configured": settings.smtp_configured},
    }


@meta_router.get("/analytics/overview")
def analytics_overview(account: str = Depends(account_optional)) -> dict:
    """Internal workflow metrics only (PRD 6.8: "clearly distinguish
    internal workflow metrics from Qoneqt viewership metrics" - we have no
    access to real Qoneqt viewership data, so none is shown or fabricated
    here). Scoped to the caller's own jobs."""
    jobs = [job for job in job_manager.list() if _owns(job, account)]
    by_status: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    by_language: dict[str, int] = {}
    for job in jobs:
        by_status[job.status.value] = by_status.get(job.status.value, 0) + 1
        by_tier[job.motion_tier.value] = by_tier.get(job.motion_tier.value, 0) + 1
        by_language[job.language.value] = by_language.get(job.language.value, 0) + 1

    return {
        "total_jobs": len(jobs),
        "by_status": by_status,
        "by_tier": by_tier,
        "by_language": by_language,
        "note": "internal workflow metrics only - no Qoneqt viewership data is available or shown",
    }


@meta_router.get("/ready")
def ready() -> JSONResponse:
    """Readiness check: can this process actually do work, not just answer
    HTTP (PRD 11 Observability: 'health/readiness endpoints')."""
    checks: dict[str, bool] = {}

    try:
        from backend.utils.ffmpeg_utils import ffmpeg_path

        ffmpeg_path()
        checks["ffmpeg"] = True
    except Exception:  # noqa: BLE001
        checks["ffmpeg"] = False

    if settings.mongodb_uri:
        try:
            import pymongo

            client = pymongo.MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            checks["mongodb"] = True
        except Exception:  # noqa: BLE001
            checks["mongodb"] = False
    else:
        checks["mongodb"] = None  # not configured - in-memory/SQLite mode, not a failure

    ready_state = checks["ffmpeg"] and checks["mongodb"] is not False
    status_code = 200 if ready_state else 503
    return JSONResponse(status_code=status_code, content={"ready": ready_state, "checks": checks})

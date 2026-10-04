from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from backend.core import docstore, plans, security

_COLL = "users"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 6


class UserExistsError(Exception):
    pass


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate(email: str, password: str) -> str:
    """Return the normalised email or raise ValueError with a user-facing reason."""
    clean = normalize_email(email)
    if not _EMAIL_RE.match(clean) or len(clean) > 254:
        raise ValueError("enter a valid email address")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > 200:
        raise ValueError("password is too long")
    return clean


def register(email: str, password: str, *, verified: bool = True) -> dict:
    clean = validate(email, password)
    doc = {
        "email_verified": verified,
        "email": clean,
        "password_hash": security.hash_password(password),
        "plan": plans.FREE_PLAN_ID,
        "plan_expires_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if not docstore.insert(_COLL, clean, doc):
        raise UserExistsError(clean)
    return doc


def get(email: str) -> dict | None:
    return docstore.get(_COLL, normalize_email(email))


def authenticate(email: str, password: str) -> dict | None:
    user = get(email)
    stored = user["password_hash"] if user else security.DUMMY_HASH
    ok = security.verify_password(password or "", stored)
    return user if (user and ok) else None


def effective_plan(user: dict) -> str:
    """The plan the account can actually use right now: a paid plan whose
    period has lapsed counts as Free."""
    plan_id = user.get("plan") or plans.FREE_PLAN_ID
    expires = user.get("plan_expires_at")
    if plan_id != plans.FREE_PLAN_ID and expires:
        if datetime.fromisoformat(expires) < datetime.now(timezone.utc):
            return plans.FREE_PLAN_ID
    return plan_id


def activate_plan(email: str, plan_id: str) -> dict | None:
    """Switch the account to a paid plan for its period. Renewing the plan the
    account is already on extends from the current expiry instead of resetting it."""
    plan = plans.plan_def(plan_id)
    if plan is None or plan.period_days is None:
        raise ValueError(f"unknown paid plan: {plan_id}")
    user = get(email)
    if user is None:
        return None
    start = datetime.now(timezone.utc)
    if effective_plan(user) == plan_id and user.get("plan_expires_at"):
        start = max(start, datetime.fromisoformat(user["plan_expires_at"]))
    expires = start + timedelta(days=plan.period_days)
    return docstore.update(_COLL, user["email"], {"plan": plan_id, "plan_expires_at": expires.isoformat()})


# --- email verification -----------------------------------------------------
# A new account gets a 6-digit code by email and can't sign in (or receive its signup credits)
# until it is confirmed, which stops throwaway accounts. Only a keyed hash of the code is stored,
# codes expire, and each code allows a handful of guesses.

MAX_CODE_ATTEMPTS = 5


class VerificationError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


def is_verified(user: dict) -> bool:
    # Accounts created before verification existed have no flag: they stay valid.
    return bool(user.get("email_verified", True))


def _code_hash(email: str, code: str) -> str:
    return hmac.new(security._secret(), f"verify:{email}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def start_verification(email: str, ttl_minutes: int) -> str:
    """Issue a fresh code for an unverified account (replacing any earlier one) and return it."""
    clean = normalize_email(email)
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    docstore.update(_COLL, clean, {"verification": {"hash": _code_hash(clean, code), "expires_at": expires.isoformat(), "attempts": 0}})
    return code


def confirm_code(email: str, code: str) -> dict:
    """Check a code; on success mark the account verified and return it."""
    clean = normalize_email(email)
    user = get(clean)
    if user is None:
        raise VerificationError(404, "no account is waiting for verification with this email")
    if is_verified(user):
        raise VerificationError(409, "this email is already verified - sign in instead")
    pending = user.get("verification") or {}
    if not pending.get("hash"):
        raise VerificationError(400, "no code has been sent yet - request a new one")
    if datetime.fromisoformat(pending["expires_at"]) < datetime.now(timezone.utc):
        raise VerificationError(410, "this code has expired - request a new one")
    attempts = int(pending.get("attempts", 0))
    if attempts >= MAX_CODE_ATTEMPTS:
        raise VerificationError(429, "too many wrong codes - request a new one")
    if not hmac.compare_digest(pending["hash"], _code_hash(clean, (code or "").strip())):
        docstore.update(_COLL, clean, {"verification": {**pending, "attempts": attempts + 1}})
        left = MAX_CODE_ATTEMPTS - attempts - 1
        raise VerificationError(400, f"that code is not right ({left} {'try' if left == 1 else 'tries'} left)")
    return docstore.update(
        _COLL, clean,
        {"email_verified": True, "verification": None, "verified_at": datetime.now(timezone.utc).isoformat()},
    )


def delete(email: str) -> None:
    docstore.delete(_COLL, normalize_email(email))


# --- external identity providers (Clerk / Google) -----------------------------


def ensure_external(email: str, provider: str) -> tuple[dict, bool]:
    """Find or create the account for an email the identity provider has already verified.

    Returns (user, activated): activated is True when the account became usable just now (created,
    or a pending sign-up confirmed), i.e. when the signup bonus is due. A new account gets an unguessable random password (the user can only
    sign in through the provider until they set one). An existing *unverified* account is marked
    verified and its password is replaced: whoever started that sign-up never proved they own the
    address, so they must not keep a password to an account the real owner now uses."""
    clean = normalize_email(email)
    if not _EMAIL_RE.match(clean) or len(clean) > 254:
        raise ValueError("the identity provider returned an invalid email address")
    now = datetime.now(timezone.utc).isoformat()
    existing = get(clean)
    if existing is None:
        doc = {
            "email_verified": True,
            "email": clean,
            "password_hash": security.hash_password(secrets.token_urlsafe(32)),
            "plan": plans.FREE_PLAN_ID,
            "plan_expires_at": None,
            "created_at": now,
            "verified_at": now,
            "auth_providers": [provider],
        }
        if docstore.insert(_COLL, clean, doc):
            return doc, True
        existing = get(clean)  # lost a race with a concurrent sign-up
        if existing is None:
            raise UserExistsError(clean)
    changes: dict = {}
    activated = not is_verified(existing)
    if activated:
        changes.update({
            "email_verified": True,
            "verification": None,
            "verified_at": now,
            "password_hash": security.hash_password(secrets.token_urlsafe(32)),
        })
    providers = list(existing.get("auth_providers") or [])
    if provider not in providers:
        changes["auth_providers"] = providers + [provider]
    if changes:
        existing = docstore.update(_COLL, clean, changes) or {**existing, **changes}
    return existing, activated

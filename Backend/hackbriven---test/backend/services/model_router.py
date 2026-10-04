from __future__ import annotations

import logging
import re
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Callable, TypeVar

from backend.core.exceptions import AllProvidersFailedError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# When set (the pipeline sets it for the duration of one job), every provider
# attempt is reported here as {"stage", "provider", "ok", "error"} so the job
# can show - as fact, not simulation - which provider failed and which one
# the chain fell through to.
attempt_sink: ContextVar[Callable[[dict], None] | None] = ContextVar("attempt_sink", default=None)

# Provider errors are echoed into logs, job error reasons and the API, and
# httpx puts the full request URL (including ?key=... query params) in its
# exception text. Scrub anything that looks like a credential before it goes anywhere.
_SECRET_PATTERNS = [
    (re.compile(r"(?i)\b(key|api_key|apikey|token|access_token|secret)=([^&\s'\"]+)"), r"\1=***"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]+"), r"\1 ***"),
]
_MAX_ERROR_CHARS = 300


def redact(text: str) -> str:
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


@dataclass(frozen=True)
class Provider:
    name: str
    call: Callable[[], T]
    # >0: after this provider fails, skip it for this many seconds (a circuit breaker for
    # providers that hang or are out of credit, so one bad provider can't tax every scene).
    cooldown_seconds: float = 0.0


_cooldown_lock = threading.Lock()
_cooldown_until: dict[tuple[str, str], float] = {}


def _cooling_down(stage: str, name: str) -> float:
    """Seconds left on this provider's cool-down (0 = available)."""
    with _cooldown_lock:
        return max(0.0, _cooldown_until.get((stage, name), 0.0) - time.monotonic())


def _start_cooldown(stage: str, name: str, seconds: float) -> None:
    if seconds > 0:
        with _cooldown_lock:
            _cooldown_until[(stage, name)] = time.monotonic() + seconds


def _clear_cooldown(stage: str, name: str) -> None:
    with _cooldown_lock:
        _cooldown_until.pop((stage, name), None)


def reset_cooldowns() -> None:
    """Test hook / operator reset."""
    with _cooldown_lock:
        _cooldown_until.clear()


def _report(stage: str, provider: str, ok: bool, error: str | None) -> None:
    sink = attempt_sink.get()
    if sink is None:
        return
    try:
        # Key-pool providers are named "eightscale[2/3]"; the pool position is
        # noise for the chain view, which shows one node per provider.
        sink({"stage": stage, "provider": re.sub(r"\[\d+/\d+\]$", "", provider), "ok": ok, "error": error})
    except Exception:  # noqa: BLE001 - observability must never break generation
        logger.exception("provider attempt sink failed")


def call_with_fallback(providers: list[Provider], *, stage: str) -> T:
    """Try each provider in order; return the first success.

    Raises AllProvidersFailedError with every collected error if the whole
    chain is exhausted. This is the single implementation of the
    Gemini->Groq / NVIDIA->Pollinations / fal.ai->Ken-Burns pattern; stage
    services must never call a provider SDK directly (see RULES.md #2).
    """
    if not providers:
        raise AllProvidersFailedError(stage, [("<none>", "no providers configured")])

    errors: list[tuple[str, str]] = []
    for provider in providers:
        remaining = _cooling_down(stage, provider.name) if provider.cooldown_seconds else 0.0
        if remaining > 0:
            message = f"skipped: failed recently, will retry in {int(remaining)}s"
            errors.append((provider.name, message))
            _report(stage, provider.name, False, message)
            continue
        try:
            logger.info("stage=%s trying provider=%s", stage, provider.name)
            result = provider.call()
        except Exception as exc:  # noqa: BLE001 - intentional: any provider failure falls through
            message = redact(str(exc))
            logger.warning("stage=%s provider=%s failed: %s", stage, provider.name, message)
            errors.append((provider.name, message))
            _report(stage, provider.name, False, message[:_MAX_ERROR_CHARS])
            _start_cooldown(stage, provider.name, provider.cooldown_seconds)
            continue
        _clear_cooldown(stage, provider.name)
        _report(stage, provider.name, True, None)
        return result

    raise AllProvidersFailedError(stage, errors)


def models_to_try(primary: str, fallbacks: object) -> list[str]:
    """The primary model followed by its comma-separated fallbacks (deduplicated, order kept).
    Anything that isn't a string (e.g. a mocked setting in tests) means "no fallbacks"."""
    extra = [m.strip() for m in fallbacks.split(",")] if isinstance(fallbacks, str) else []
    ordered: list[str] = []
    for model in [primary, *extra]:
        if model and model not in ordered:
            ordered.append(model)
    return ordered


def try_models(call: Callable[[str], T], models: list[str]) -> T:
    """Run `call(model)` for each model until one succeeds; re-raise the last error.
    One overloaded/retired model must not take its whole provider out of the chain."""
    last: Exception | None = None
    for model in models:
        try:
            return call(model)
        except Exception as exc:  # noqa: BLE001 - try the provider's next model
            last = exc
            logger.info("model %s failed (%s), trying the next one", model, redact(str(exc))[:120])
    raise last or RuntimeError("no model configured")

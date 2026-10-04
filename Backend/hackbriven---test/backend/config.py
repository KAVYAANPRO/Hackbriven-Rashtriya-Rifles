from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_key_pool(plural_csv: str, singular: str) -> list[str]:
    """Comma-separated multi-account key pool, falling back to the single
    legacy key field when no pool is configured. Blank entries (trailing
    commas, accidental double commas) are dropped."""
    keys = [k.strip() for k in plural_csv.split(",") if k.strip()] if plural_csv else []
    if not keys and singular:
        keys = [singular]
    return keys


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    # Tried in order after GEMINI_MODEL when it is overloaded (503), rate-limited or retired.
    gemini_fallback_models: str = "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-flash-lite-latest"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_fallback_models: str = "openai/gpt-oss-20b,qwen/qwen3.8-27b"
    groq_whisper_model: str = "whisper-large-v3-turbo"

    openrouter_api_key: str = ""
    openrouter_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    openrouter_fallback_models: str = "qwen/qwen3.8-27b:free"

    nvidia_api_key: str = ""
    nvidia_image_model: str = "black-forest-labs/flux.1-dev"
    # NVIDIA's hosted image endpoints can hang for minutes when overloaded; fail fast so the
    # chain moves on instead of stalling every scene.
    nvidia_image_timeout_seconds: float = 25.0

    # Cloudflare Workers AI image generation - FREE (10,000 neurons/day, no credit card;
    # FLUX.1 [schnell] costs ~45-60 neurons per image, i.e. ~200 images/day). Create a free
    # Cloudflare account, copy the Account ID, and make an API token with "Workers AI" permission.
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    # Extra Cloudflare accounts tried in order after the one above when its daily allowance runs out
    # or it fails: comma-separated "ACCOUNT_ID:API_TOKEN" pairs.
    cloudflare_accounts: str = ""
    cloudflare_image_models: str = "@cf/black-forest-labs/flux-1-schnell"
    # FLUX.1 [schnell] diffusion steps (max 8). More steps = finer detail; each step costs ~9.6 neurons.
    cloudflare_flux_steps: int = 8
    # Which image providers may be used, in order. "cloudflare" alone means every scene image comes
    # from Cloudflare Workers AI (with retries); only if it is completely unavailable does the job
    # fall back to a local title card, never to another AI service.
    image_providers: str = "cloudflare,openrouter,nvidia,pollinations"
    # Keyless last resort before the plain gradient card. Its free tier only returns small
    # watermarked squares, so it is only used when every better provider has failed.
    image_use_pollinations: bool = True

    # OpenRouter image generation (POST /api/v1/images), tried first when OPENROUTER_API_KEY is set.
    # Comma-separated, in order. Needs a purchased OpenRouter balance - a never-funded (free-tier)
    # account is refused with HTTP 402, which just moves the chain on to the next provider.
    # Defaults are strong, inexpensive models (listed around $0.003 per image on OpenRouter).
    openrouter_image_models: str = "bytedance-seed/seedream-5-0-pro,qwen/qwen-image-3-pro"
    # After a provider fails, skip it this long (seconds) instead of paying its timeout on every scene.
    provider_cooldown_seconds: float = 600.0

    # Resolution enhancement (all done server-side; the UI never names the service).
    # Motion clips from the video providers are only 480p - enhance them before they're spliced in.
    enhance_motion_clips: bool = True
    # fal.ai video upscaler used for motion clips and the 4K export (needs FAL_API_KEY with credit).
    upscale_fal_endpoint: str = "fal-ai/topaz/upscale/video"
    upscale_timeout_seconds: float = 600.0

    # Live-verified against the real edge-tts voice catalog (listed, not
    # guessed): hi-IN voices expect Devanagari script; en-IN reads Latin-
    # script Hinglish with an Indian accent, which is what Hinglish actually
    # needs (a hi-IN voice fed Latin-script text mispronounces badly).
    edge_tts_voice: str = "en-US-AriaNeural"
    edge_tts_voice_hi: str = "hi-IN-SwaraNeural"
    edge_tts_voice_hinglish: str = "en-IN-NeerjaNeural"

    whisper_model: str = "base"  # local faster-whisper fallback

    fal_api_key: str = ""
    fal_motion_model: str = "fal-ai/ltx-video"

    # 8scale.com (Wan 2.2 14B image-to-video): 10 free generations per key,
    # no card. Tried first - genuinely free right now, unlike Magic Hour
    # below, whose 400 free credits were exhausted during development.
    # EIGHTSCALE_API_KEYS (comma-separated) is a pool of keys from multiple
    # free accounts - each account's free quota is small, so generate_
    # motion_clip() rotates through the whole pool before falling through
    # to Magic Hour, multiplying the effective free capacity instead of
    # stopping the moment one account's quota is spent. EIGHTSCALE_API_KEY
    # (singular) still works as a one-key pool for backward compatibility.
    eightscale_api_key: str = ""
    eightscale_api_keys: str = ""
    eightscale_model: str = "wan-2.2/14b/image-to-video"
    eightscale_resolution: str = "480p"

    magic_hour_api_key: str = ""
    magic_hour_api_keys: str = ""  # same pooling pattern as eightscale_api_keys above
    magic_hour_resolution: str = "480p"
    # Real generative video is credit-metered (free tier: 400 credits,
    # ~120/5s clip at 480p) - cap how many scenes per job use it so one
    # video can't silently burn through the whole balance. Remaining
    # scenes fall back to Ken Burns, same resilience pattern as every
    # other stage.
    magic_hour_max_scenes_per_job: int = 2

    # Razorpay: client-facing credit top-ups. Use a rzp_test_ key first -
    # test mode charges nothing real and is otherwise identical.
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    # One top-up package: pay this many paise (INR x100), receive this many
    # platform credits. Placeholder pricing - adjust freely, the payment
    # mechanism doesn't depend on these numbers.
    razorpay_package_amount_paise: int = 9900  # ₹99
    razorpay_package_credits: int = 50

    # Credits ledger backing store. When set, backend/core/credits.py uses
    # this MongoDB instead of a local SQLite file - needed because this
    # pipeline is designed to deploy on Hugging Face Spaces, whose storage
    # is typically ephemeral (wiped on redeploy/restart), which would lose
    # a real paying balance. SQLite remains the fallback for local dev with
    # no URI configured.
    mongodb_uri: str = ""
    mongodb_db_name: str = "citysetu"

    # Shared-secret auth for mutating endpoints (create/approve/publish/cancel,
    # credit top-ups). Empty means auth is disabled - fine for local dev and
    # the existing test suite, but must be set before any real deployment;
    # has_auth / require_auth below make that gap visible instead of silent.
    backend_api_key: str = ""

    # Browser origins allowed to call this API directly (comma-separated).
    # The Vite dev server proxies /api so it never needs CORS locally; this
    # matters when the frontend is deployed on a different origin.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"

    # User accounts (email + password -> signed session token). The signing
    # secret defaults to a random value persisted in the storage dir; set
    # SESSION_SECRET explicitly on any host whose disk is ephemeral, or every
    # restart will sign everyone out.
    session_secret: str = ""
    session_ttl_hours: int = 24 * 14
    # False keeps the pre-accounts behaviour (anonymous callers share one
    # "default" account). True makes every user-scoped endpoint need a login.
    require_login: bool = False
    # Accounts with the master-admin role (comma-separated emails): they alone see the provider
    # "Orchestra" view and the admin endpoints.
    admin_emails: str = ""
    signup_credits: int = 20  # credits granted once to every new account (the Free plan's starter balance)

    # Outgoing email (sign-up verification codes). Gmail: SMTP_HOST=smtp.gmail.com, SMTP_PORT=587,
    # SMTP_SECURITY=starttls, SMTP_USER=<address>, SMTP_PASSWORD=<16-char App Password>.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: str = "starttls"  # starttls | ssl | none
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # defaults to smtp_user
    smtp_from_name: str = "IdeaFeed AI"
    # "auto" = new accounts must confirm their email whenever SMTP is configured; "on" / "off" force it.
    email_verification: str = "auto"
    verification_code_ttl_minutes: int = 15

    # Reference-image uploads
    max_upload_images: int = 8
    max_upload_bytes: int = 10 * 1024 * 1024

    storage_dir: str = "storage/jobs"
    target_width: int = 1080
    target_height: int = 1920
    max_regenerate_attempts: int = 2

    provider_timeout_seconds: float = 30.0

    @property
    def storage_path(self) -> Path:
        path = Path(self.storage_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and (self.smtp_from or self.smtp_user))

    @property
    def email_verification_enabled(self) -> bool:
        mode = self.email_verification.lower()
        if mode == "on":
            return True
        if mode == "off":
            return False
        return self.smtp_configured

    @property
    def cloudflare_account_pool(self) -> list[tuple[str, str]]:
        """Every configured Cloudflare (account_id, api_token) pair, primary first, no duplicate pairs.
        One account may appear with several tokens: they share that account's daily allowance, so a
        second token is a backup if the first is revoked or failing, not extra quota."""
        pool: list[tuple[str, str]] = []
        if self.cloudflare_account_id and self.cloudflare_api_token:
            pool.append((self.cloudflare_account_id.strip(), self.cloudflare_api_token.strip()))
        for entry in self.cloudflare_accounts.replace("\n", ",").split(","):
            account_id, sep, token = entry.strip().partition(":")
            pair = (account_id.strip(), token.strip())
            if sep and all(pair) and pair not in pool:
                pool.append(pair)
        return pool

    @property
    def has_cloudflare(self) -> bool:
        return bool(self.cloudflare_account_pool)

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def image_provider_list(self) -> list[str]:
        return [p.strip().lower() for p in self.image_providers.split(",") if p.strip()]

    @property
    def cloudflare_image_model_list(self) -> list[str]:
        return [m.strip() for m in self.cloudflare_image_models.split(",") if m.strip()]

    @property
    def openrouter_image_model_list(self) -> list[str]:
        return [m.strip() for m in self.openrouter_image_models.split(",") if m.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_fal(self) -> bool:
        return bool(self.fal_api_key)

    @property
    def has_razorpay(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def has_auth(self) -> bool:
        return bool(self.backend_api_key)

    @property
    def eightscale_key_pool(self) -> list[str]:
        return _parse_key_pool(self.eightscale_api_keys, self.eightscale_api_key)

    @property
    def magic_hour_key_pool(self) -> list[str]:
        return _parse_key_pool(self.magic_hour_api_keys, self.magic_hour_api_key)


settings = Settings()

# INTEGRATION.md — IdeaFeed AI frontend ⇄ backend

The React app (this folder) talks to the FastAPI backend in `Backend/hackbriven---test`.
This file is the API contract both sides are built against.

## Running it

```bash
# 1) backend  (http://127.0.0.1:8000, docs at /docs)
cd Backend/hackbriven---test
pip install -r requirements.txt
python -m uvicorn backend.api.main:app --port 8000

# 2) frontend (http://localhost:3000)
cd ../..
npm install
npm run dev
```

The Vite dev server proxies `/api/*` → `http://127.0.0.1:8000/*`, so the browser never makes a
cross-origin call in dev. For a separate deployment set `VITE_API_URL=https://your-backend` at build time
(the backend also has CORS, configured with `CORS_ORIGINS`).

## Conventions

* JSON everywhere except uploads (multipart), media (binary) and the handoff (text).
* Auth header: `Authorization: Bearer <session token>` (token comes from `/auth/register` or `/auth/login`).
  `<video>`/`<img>` tags cannot send headers, so media URLs carry `?sig=<job.media_sig>` instead.
* Errors are FastAPI style: `{"detail": "text"}` or `{"detail": {...}}`.
  * `401` not signed in / bad token · `402` not enough credits · `403` plan can't use that tier ·
    `404` not found · `409` wrong state · `413/415/422` bad input · `503` provider not configured.
* The backend is the source of truth for **prices, plans, tiers and credits** — the UI must read them
  from `GET /plans` and `GET /credits`, never hard-code them.

## Endpoints

### Meta (public)
| Call | Response |
|---|---|
| `GET /health` | `{status:"ok"}` |
| `GET /ready` | `{ready:bool, checks:{ffmpeg:bool, mongodb:bool\|null}}` (HTTP 503 when `ready` is false) |
| `GET /providers/status` | per stage `{chain:[names], configured:{name:bool}}` for `script`, `image`, `voice`, `captions`, `motion` (+`motion.key_pool_size`); `payments:{razorpay_configured}`; `persistence:{mongodb_configured}`; `auth:{enabled}` (legacy shared key); `accounts:{enabled:true}` |
| `GET /plans` | `{cost_by_tier:{basic,balanced,max}, plans:[{id,name,price_paise,credits,period_days\|null,tiers:[...]}], packs:[{id,credits,price_paise}], payments:{razorpay_configured}}` |

### Accounts
| Call | Body | Response |
|---|---|---|
| `POST /auth/register` | `{email,password}` (password ≥ 6) | `{token,user}` · `409` email exists · `422` invalid |
| `POST /auth/login` | `{email,password}` | `{authenticated:true,auth_required:bool,token,user}` · `401` bad credentials |
| `GET /auth/me` | – | `user` · `401` |

`user = {email, plan:"free"|"pro"|"studio", plan_expires_at:iso|null, balance:int, created_at:iso}`.
New accounts start on `free` with the signup credit bonus (20). A paid plan lasts `period_days`, then drops back to `free`.

### Credits & payments (Razorpay)
| Call | Body | Response |
|---|---|---|
| `GET /credits` | – | `{balance, cost_by_tier, plan, plan_expires_at, tiers_allowed:[...], packs:[...]}` |
| `POST /credits/create-order` | `{pack:<pack id>}` **or** `{plan:"pro"\|"studio"}` | `{order_id,amount,currency,key_id,credits,kind:"pack"\|"plan",plan?}` · `503` Razorpay not configured |
| `POST /credits/verify-payment` | `{razorpay_order_id,razorpay_payment_id,razorpay_signature}` | `{balance,plan,plan_expires_at,credits_added,already_processed}` · `400` bad signature · `404` unknown order |

Flow: `create-order` → open Razorpay Checkout.js with `key_id`/`order_id`/`amount` → in its `handler` call
`verify-payment` with the three values Razorpay returns. Credits are added only after verification. Verifying
the same order twice never credits twice.

### Jobs
| Call | Notes |
|---|---|
| `POST /jobs` | body `{topic, language:"en"\|"hi"\|"hinglish", motion_tier:"basic"\|"balanced"\|"max", reference_images?:[upload ids]}`; header `Idempotency-Key` (a repeat returns the original job, no second charge). `402 {detail:{message,required,available,top_up}}`, `403 {detail:{message,required_plan,plan}}` |
| `GET /jobs` | list, newest first, only the signed-in user's jobs |
| `GET /jobs/{id}` | one job (poll every ~1.5 s while not terminal) |
| `GET /jobs/{id}/result` | `{job_id,result_path,status}` · `409` until rendered |
| `GET /jobs/{id}/quality-report` | `{passed,width,height,duration_seconds,has_audio_track,reasons[]}` · `409` until validated |
| `GET /jobs/{id}/video?sig=` | `video/mp4`, supports HTTP Range. `&download=1` forces a download |
| `GET /jobs/{id}/scenes/{index}/image?sig=` | `image/png` of the scene visual (404 until generated) |
| `GET /jobs/{id}/handoff?sig=` | the manual handoff note as a `.txt` download (409 before publish) |
| `POST /jobs/{id}/approve` | `{approver}` — only from `done` |
| `POST /jobs/{id}/cancel` | not allowed from terminal states (409) |
| `POST /jobs/{id}/publish` | allowed from `approved` **and** `publish_failed` (retry). Always ends in `manual_handoff` (Qoneqt has no publishing API) — never `published`. Repeating on a `manual_handoff` job just returns it |

#### Job object
```
id, topic, language, motion_tier, status, created_at, updated_at,
history: [{stage, status, at}],
script:      null | {topic, hook, mood, scenes:[{index,narration,image_prompt,duration_seconds,mood}]},
scene_plan:  null | {topic, hook, scenes:[{index,narration,image_prompt,duration_seconds,start_offset_seconds,end_offset_seconds}]},
quality_report: null | {passed,width,height,duration_seconds,has_audio_track,reasons[]},
result_path, error_stage, error_reason, idempotency_key,
approved_by, approved_at, published_at, publish_error, manual_handoff_path, manual_handoff_note,
owner, reference_images:[ids],
provider_events: [{stage, provider, ok, error|null, at}],   // real fallback attempts, in order
media_sig, ready_scene_images:[int], has_video:bool          // added by the API, used to build media URLs
```
`status`: `queued → running_intelligence → running_generation → running_composition → running_validation → done → approved → manual_handoff`
(+ `failed`, `cancelled`, `publishing`, `published`, `publish_failed`).

`history` entries: `{stage:"input",status:"accepted"}` first; then `{stage:"running_…"|"done",status:"entered"}` per stage;
`{stage:"approved",status:"approved by X"}`; `{stage:"cancelled",…}`; on failure `{stage:<error_stage>,status:"failed: <reason>"}`.
`error_stage` looks like `generation.image`, `intelligence.story_engine`, `composition.ken_burns`, `validation.quality_gate`, `pipeline`.

### Uploads, prompt boost, analytics
| Call | Notes |
|---|---|
| `POST /uploads` | multipart field `files` (repeatable). ≤ 8 images, ≤ 10 MB each, real images only. → `{files:[{id,name,size,width,height}]}`. Pass the ids as `reference_images` to `POST /jobs`. Reference images become the visuals of the first scenes (in order); remaining scenes are AI-generated. |
| `POST /prompt/boost` | `{prompt, language?}` → `{text, source:"gemini"\|"groq"\|"openrouter"\|"local"}` — rewrites a rough idea into a richer prompt through the backend's provider chain; `local` = deterministic fallback, not AI |
| `GET /analytics/overview` | `{total_jobs, by_status, by_tier, by_language, note}` — internal workflow metrics for the signed-in user only; no Qoneqt viewership data exists |

## v2 additions: styles, resolution, download formats

All three lists below come from `GET /plans` (never hard-code them in the UI):

```
GET /plans -> {
  ...existing fields...,
  styles:      [{id, label, description, group}],            // e.g. cinematic, minimalist, playful, 3d, colorful ... plus "auto" and "custom"
  resolutions: [{id, label, width, height, credit_surcharge}], // "720p" | "1080p" | "4k"
  formats:     [{id, label, ext, description, kind}],         // mp4, mov, webm, mkv, gif, mp3 (kind: "video" | "animation" | "audio")
  plans: [{..., resolutions:[ids]}]                           // which resolutions a plan may use (4k is paid-only)
}
GET /credits -> {..., resolutions_allowed:[ids]}
```

**Create a job** (`POST /jobs`) takes three new optional fields:
`style` (id from `styles`, default `"auto"`), `style_prompt` (only for `style:"custom"`, max 300 chars),
`resolution` (id from `resolutions`, default `"1080p"`). The job's price is `cost_by_tier[tier] + resolution.credit_surcharge`.
Errors: `403 {detail:{message, required_plan, plan}}` when the plan can't use that tier **or** resolution.
The job object returns `style`, `style_prompt`, `resolution`, and `quality_report.width/height` reflect the delivered file.

**Download in another format**: `GET /jobs/{id}/download?format=<id>&sig=<media_sig>` -> the video converted to that
container/codec (converted on first request, then cached; may take a few seconds for large files, so show a busy state).
`format=mp4` returns the stored master. Unknown format -> 422; job has no video yet -> 409.

**Prompt boost** (`POST /prompt/boost`) accepts optional `style` (id) and `language` and uses them when rewriting.

The user must never be told that any step uses a third-party service for upscaling: the UI only says "4K", "Enhanced", etc.

## Frontend ⇄ endpoint map

| Screen / feature | Endpoints it uses |
|---|---|
| App boot, session restore | `GET /auth/me` (saved token), `GET /plans`, `GET /providers/status`, `GET /ready` (falls back to `GET /health`) every 20 s |
| Landing (tier chart) | `GET /plans` (public) |
| Login / create account | `POST /auth/login`, `POST /auth/register` |
| Top bar + sidebar (credits, plan, system status) | `GET /credits` (every 30 s and on focus), `GET /ready` |
| Create → Boost | `POST /prompt/boost` (or the browser-side Gemini call if the user saved their own key in Settings) |
| Create → reference images | `POST /uploads` (multipart) → ids sent as `reference_images` |
| Create → Generate | `POST /jobs` with an `Idempotency-Key`; 402 → top-up prompt, 403 → plan prompt |
| Jobs list | `GET /jobs` (every 3 s while any job is running), `GET /jobs/{id}/scenes/0/image` thumbnails |
| Job detail | `GET /jobs/{id}` (every 1.5 s until terminal), `GET /jobs/{id}/quality-report`, `GET /jobs/{id}/video`, `GET /jobs/{id}/scenes/{i}/image`, `GET /jobs/{id}/handoff` |
| Job actions | `POST /jobs/{id}/approve`, `/cancel`, `/publish` (also the retry from `publish_failed`) |
| Credits & billing | `GET /plans`, `GET /credits`, `POST /credits/create-order` → Razorpay Checkout → `POST /credits/verify-payment` |
| Orchestra | `GET /providers/status`, `GET /ready`, and the `provider_events` of real jobs for the reroute replay |
| Analytics | `GET /analytics/overview` |
| Settings | `GET /providers/status` (shows the legacy API-key field only if `auth.enabled`), `GET /auth/me` |

`GET /jobs/{id}/result` exists for API consumers; the UI doesn't need it because the job object carries `has_video`.

## Known limits (stated plainly)

* Qoneqt has no publishing API, so "Publish" always ends in `manual_handoff` with a downloadable note, never `published`.
* Plans are one-off 30-day purchases, not auto-renewing subscriptions. Credits never expire.
* Reference images fill the first scenes in upload order; the script is not told about them.
* Failed jobs are not refunded and cannot resume from the failed stage (re-submit instead).
* No password reset or email verification yet.

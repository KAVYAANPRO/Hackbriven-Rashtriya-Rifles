# FRONTEND_PRD.md — IdeaFeed AI Frontend

**Status:** specification, not yet built. The current UI (`frontend/app.py`,
Gradio) is a functional placeholder that exercises every backend endpoint
but was never meant to be the judge-facing product. This document specs
the real one: a high-production-value web app that covers **every
capability the backend already has**, with a visual bar that matches a
premium creative tool (Runway, Pika, CapCut, ElevenLabs Studio), not a
dev-tool form.

Backend reference: `DEPLOYMENT.md` (API surface, provider chains, job
lifecycle). This document assumes that backend as-is and does not ask for
new endpoints — every screen below maps to something that already exists
and already works.

---

## 1. Vision

Open the app, type an idea, watch it become a reviewed, publish-ready
video — and *feel* the machinery working. The one feature competitors
won't have: a live, honest view of the AI provider fallback chain
("AI orchestra") actually rerouting around a failure in real time. That
moment — a provider going red, the next one lighting up, the job
finishing anyway — is the single most important visual beat in the whole
product. It is proof, not decoration, so it must look worth watching.

## 2. Design direction ("high graphics")

### 2.1 Mood

Dark-first, cinematic, confident. Big video previews. Motion that reads as
*system activity* (pipeline stages lighting up, providers pulsing,
progress bars with real physics) rather than decorative animation for its
own sake. Think a video-editing cockpit crossed with an observability
dashboard — not a form with a submit button.

### 2.2 Design tokens

| Token | Value | Use |
|---|---|---|
| `--bg-base` | `#0A0A0F` | App background |
| `--bg-surface` | `#15151D` | Cards, panels |
| `--bg-surface-raised` | `#1E1E29` | Modals, popovers |
| `--accent-primary` | `#7C5CFF` → `#FF5CA8` gradient | Primary actions, active states |
| `--accent-success` | `#2EE6A8` | Done / passed / published |
| `--accent-warning` | `#FFB84D` | Needs review / manual handoff |
| `--accent-danger` | `#FF5C72` | Failed / publish_failed |
| `--text-primary` | `#F5F5FA` | Headings, primary text |
| `--text-muted` | `#8E8EA0` | Secondary text, labels |
| Typography | `Inter` (UI), `JetBrains Mono` (job IDs, provider names, logs) | — |
| Radius | 16px cards, 999px pills (status badges) | — |
| Motion | 200–320ms, `cubic-bezier(0.16, 1, 0.3, 1)` ease-out | All transitions |

### 2.3 Principles

1. **Every async wait has a purpose-built animation**, never a generic
   spinner — script generation shows text being "typed," image generation
   shows a shimmering placeholder resolving into the real image, motion
   generation shows a subtle Ken-Burns preview *while it renders*.
2. **State is always visible at a glance** — a persistent status rail
   shows job stage, credits balance, and system readiness without
   navigating away.
3. **Nothing fakes progress.** If a stage is slow, show real elapsed time,
   not a progress bar that lies (this mirrors the backend's own "never
   fake a result" rule — see `RULES.md`).
4. **Failures are shown as recoveries, not dead ends** — when a provider
   falls back, animate it as a reroute, not a red error toast.

---

## 3. Information architecture

```
/                      Create (home) — topic input, settings, generate
/jobs                  Job library — every past job, filterable
/jobs/:id              Job detail — live progress -> preview -> review -> publish
/orchestra             AI Orchestra — live provider fallback status
/analytics             Analytics overview — internal metrics dashboard
/credits               Credits & billing — balance, top-up via Razorpay
/settings              Auth key (if BACKEND_API_KEY is set), language/tier defaults
```

A persistent top bar (all routes) shows: system status dot (`/ready`),
credits balance (`/credits`), and active-job indicator if one is running.

---

## 4. Screens, mapped to backend capability

Every item below cites the exact endpoint(s)/field(s) it covers. This
table **is** the completeness check: nothing in the backend is left
without a UI surface.

### 4.1 Create (`/`)

| Element | Backend mapping |
|---|---|
| Topic input (free text) | `POST /jobs` body `topic` |
| Language selector (English / Hindi / Hinglish) | `Language` enum — `en` / `hi` / `hinglish` |
| Motion effort selector (Basic / Balanced / Max) — shown with the real credit cost per tier inline | `MotionTier` enum + `GET /credits` `cost_by_tier` |
| Generate button — disabled with a clear reason if credits are insufficient | `POST /jobs` → 402 response (`required`/`available`/`top_up`) routes straight into the Credits screen |
| Idempotent resubmit protection (if the user double-clicks or the network retries) | `Idempotency-Key` header generated client-side per submission attempt |
| On submit → redirect to `/jobs/:id` | `POST /jobs` response `id` |

### 4.2 Job detail (`/jobs/:id`) — the core screen

A single screen that morphs through the job's entire life, matching the
full `JobStatus` state machine exactly (no state is skipped or hidden):

```
queued → running_intelligence → running_generation → running_composition
→ running_validation → done → approved → publishing → published
                                                      ↘ publish_failed
                                        ↘ manual_handoff
      ↘ failed                 ↘ cancelled (from any non-terminal state)
```

| Phase | UI | Backend mapping |
|---|---|---|
| `queued` / `running_*` | Animated stage tracker (5 stages lit up progressively), live-polled | `GET /jobs/:id` (poll every 1.5–2s), `status`, `history[]` |
| Mid-generation detail | Expandable "what's happening" panel showing the script hook as it's produced, scene count, current scene thumbnail as each image resolves | `script.hook`, `scene_plan.scenes[]` |
| `failed` | Clear failure card: stage + reason, Retry button (resubmits as a new job) | `error_stage`, `error_reason` |
| `cancelled` | Muted "cancelled" card | `status == cancelled` |
| `done` | Video player (autoplay muted preview) + **Quality Report card**: pass/fail badge, resolution, duration, audio-track check, failure reasons if any | `result_path`, `GET /jobs/:id/quality-report` |
| `done` → action | **Approve** button with approver name/email field | `POST /jobs/:id/approve` |
| `approved` | Approval receipt (who, when) + **Publish** button | `approved_by`, `approved_at` |
| `publishing`/`manual_handoff` | **Explicit, unmissable banner**: "Manual handoff — not automatically published" with the handoff note rendered (title/caption suggestion, language, motion tier) and a **Download handoff package** button | `POST /jobs/:id/publish`, `manual_handoff_note`, `manual_handoff_path` |
| `publish_failed` | Error card with `publish_error`, Retry publish button | `publish_error` |
| Any non-terminal state | **Cancel** button, confirps before firing | `POST /jobs/:id/cancel` |
| Always visible | Job metadata chip row: id, language, motion tier, created/updated timestamps | `id`, `language`, `motion_tier`, `created_at`, `updated_at` |
| Always visible (collapsible) | Full stage history timeline (every `StageTimestamp`) | `history[]` |

### 4.3 Job library (`/jobs`)

| Element | Backend mapping |
|---|---|
| Table/grid of all jobs, newest first, with thumbnail, topic, status pill, language, tier | `GET /jobs` |
| Filter by status, language, motion tier (client-side over the listed set) | same payload, filtered in-browser |
| Click row → `/jobs/:id` | — |
| Empty state with a CTA back to Create | — |

### 4.4 AI Orchestra (`/orchestra`) — the showcase screen

The visual centerpiece. Renders every stage's provider fallback chain as a
horizontal pipeline of nodes (script → image → voice → captions → motion),
each node colored by live status:

- **Green glow** — configured and currently the active/primary provider
- **Grey** — configured as fallback, idle
- **Outline only** — not configured (no key set), chain still functional
  via the next node
- **Red flash → arrow to next node** — only shown live, during an actual
  job, when a provider fails and the next one in `call_with_fallback`'s
  order takes over (this is the moment from §1)

| Element | Backend mapping |
|---|---|
| Static chain + configured/not-configured state | `GET /providers/status` |
| Live reroute animation during an active job | Correlates the currently-open job's `history[]`/stage timing with the provider chain; a visible fallback event is inferred client-side from stage duration/retry patterns surfaced by the backend logs is out of scope for v1 — v1 shows the **static chain truthfully** and animates a reroute only as a **replay** using the actual provider names from a completed job's metadata once that's exposed (see §7, deferred) |
| Auth status, Mongo persistence status | `auth.enabled`, `persistence.mongodb_configured` from the same payload |

### 4.5 Analytics (`/analytics`)

| Element | Backend mapping |
|---|---|
| Total jobs, stacked bar/donut by status | `GET /analytics/overview` → `total_jobs`, `by_status` |
| Explicit disclaimer strip: "Internal workflow metrics only — no Qoneqt viewership data available" | `note` field, rendered verbatim, not paraphrased away |

### 4.6 Credits & billing (`/credits`)

| Element | Backend mapping |
|---|---|
| Current balance, large and always-visible in the top bar too | `GET /credits` → `balance` |
| Cost-per-tier reference table | `GET /credits` → `cost_by_tier` |
| "Top up" → Razorpay Checkout modal (amount/credits from config) | `POST /credits/create-order` → Razorpay Checkout.js → `POST /credits/verify-payment` |
| Insufficient-credits redirect target from the Create screen's 402 | same endpoints |

### 4.7 Settings (`/settings`)

| Element | Backend mapping |
|---|---|
| API key field, only shown/required if the backend reports auth is on | `GET /providers/status` → `auth.enabled`; key stored client-side, sent as `Authorization: Bearer <key>` on every mutating call |
| Default language / motion tier preferences (client-side only, pre-fills Create) | no backend state — explicitly local |

### 4.8 Global status rail (every screen)

| Element | Backend mapping |
|---|---|
| System status dot (green/red) | `GET /ready` → `ready`, `checks.ffmpeg`, `checks.mongodb` |
| Liveness fallback if `/ready` itself is unreachable | `GET /health` |

---

## 5. Completeness checklist

Every backend endpoint, explicitly accounted for:

- [x] `POST /jobs` — Create screen
- [x] `GET /jobs` — Job library
- [x] `GET /jobs/:id` — Job detail (polled)
- [x] `GET /jobs/:id/result` — video player source
- [x] `GET /jobs/:id/quality-report` — Quality Report card
- [x] `POST /jobs/:id/approve` — Approve action
- [x] `POST /jobs/:id/cancel` — Cancel action
- [x] `POST /jobs/:id/publish` — Publish action / manual handoff banner
- [x] `GET /credits` — Credits screen + top bar
- [x] `POST /credits/create-order` — Top-up modal
- [x] `POST /credits/verify-payment` — Top-up modal completion
- [x] `GET /providers/status` — AI Orchestra screen + Settings auth gate
- [x] `GET /analytics/overview` — Analytics screen
- [x] `GET /ready` / `GET /health` — Global status rail

Every `Job` field, explicitly surfaced somewhere: `id`, `topic`,
`language`, `motion_tier`, `status`, `created_at`, `updated_at`,
`history`, `script`, `scene_plan`, `quality_report`, `result_path`,
`error_stage`, `error_reason`, `idempotency_key` (used, not displayed),
`approved_by`, `approved_at`, `published_at`, `publish_error`,
`manual_handoff_path`, `manual_handoff_note`.

Nothing in the current backend is without a screen.

---

## 6. Non-functional requirements

- **Polling, not fake realtime**: the backend has no SSE/WebSocket
  endpoint (`GET /jobs/:id/events` from the original Node-style PRD was
  never built — see `DEPLOYMENT.md` §13). Poll `GET /jobs/:id` every
  1.5–2s while non-terminal; stop immediately on a terminal status.
- **Optimistic UI only where safe**: Cancel shows an immediate "cancelling…"
  state but doesn't claim success until the next poll confirms
  `status == cancelled`.
- **Mobile-usable, not mobile-first**: primary usage is a demo on a laptop
  to judges; the layout must not break at phone width but can prioritize
  desktop information density.
- **No secrets ever rendered**: `providers/status` already returns only
  booleans — the frontend must never attempt to read or display an actual
  key value from anywhere.
- **Error states are never blank**: every fetch failure renders a retry
  affordance with the actual error message, never a silent blank panel.

---

## 7. Explicitly out of scope for v1

- Live reroute *detection* mid-job on the Orchestra screen (shown as a
  replay instead — see §4.4). Real-time correlation would need the
  backend to emit per-provider-attempt events, which it doesn't yet.
- File/reference-image upload (backend doesn't accept one — see
  `DEPLOYMENT.md` §13).
- Per-scene storyboard editing/regeneration (backend doesn't support it).
- Multi-user login — Settings' API key field is a single shared secret,
  not per-user auth, matching the backend exactly (`DEPLOYMENT.md` §10).
- Aspect ratio / duration / theme pickers — backend doesn't expose them.

Shipping any of these in the frontend without the backend supporting them
would misrepresent the product — consistent with this project's standing
rule to never fake a capability.

---

## 8. Recommended stack

- **React + Vite + TypeScript** — matches the original PRD's own
  recommendation (`PRD.md`/the IdeaFeed AI spec §7.2) and is the fastest
  path to the motion/graphics bar in §2.
- **Tailwind CSS** for the design tokens in §2.2.
- **Framer Motion** for the stage-tracker, orchestra reroute, and
  skeleton-to-image reveal animations in §2.3.
- **TanStack Query** for the `GET /jobs/:id` polling loop (built-in
  interval refetch, automatic stop via `enabled`/`refetchInterval`
  callback keyed on terminal status).
- **Razorpay Checkout.js** (official embed) for the top-up modal — do not
  hand-roll card collection; this app never touches raw payment details,
  matching the backend's own signature-verification design.

Replaces the current `frontend/app.py` Gradio UI entirely once built;
`app.py` (the HF Spaces/Render bundler) would then serve the built React
app as static files alongside the FastAPI backend instead of launching
Gradio.

---

## 9. Phased build plan

1. **P0** — Create screen, Job detail (full state machine + video +
   quality report + approve/publish/cancel), global status rail. This
   alone covers the entire demo path end to end.
2. **P1** — Job library, Credits screen + Razorpay modal, Analytics
   screen.
3. **P2** — AI Orchestra screen (the showcase piece — higher design
   effort, not required for the core flow to work).

## 10. Acceptance criteria

- [ ] Every endpoint in §5's checklist has a working UI surface, verified
      against the real running backend, not mocked data.
- [ ] A full job (`queued` → `done` → `approved` → `manual_handoff`) is
      completable without leaving `/jobs/:id`.
- [ ] The 402-insufficient-credits path from Create actually lands the
      user in a working Razorpay top-up flow and returns them able to
      retry generation.
- [ ] No screen ever displays a secret value, a fake metric, or a status
      that misrepresents what the backend actually returned.
- [ ] Visual design matches §2's tokens consistently across all screens
      (no screen left in default/unstyled state).

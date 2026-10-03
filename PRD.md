# PRD.md — IdeaFeed AI
## Backend-First MVP for the Qoneqt × CTRL FREAK Challenge

**Document status:** MVP specification  
**Product name:** IdeaFeed AI (working title)  
**Primary platform:** Qoneqt Global Feed  
**Product type:** AI-powered video content creation, review, publishing, and performance workflow

---

## 1. Product Overview

IdeaFeed AI turns a topic, prompt, trend, uploaded script, or reference image into a publish-ready video through a repeatable backend pipeline.

The product combines:
- LLM-powered topic analysis, scripting, hooks, and scene planning.
- Configurable video, image, and speech generation providers.
- Audio/video composition, subtitles, and quality checks.
- Human review and approval before publishing.
- Qoneqt publishing through an authorized, supported integration.
- Performance insights based only on analytics that are actually available.

The product is not considered complete merely because a video-generation screen exists. The core success path must run from input to a finished video and support publishing through an approved Qoneqt workflow.

### Product promise

**Turn an idea into a reviewed, ready-to-publish video — reliably, transparently, and with controllable generation effort.**

## 2. Problem Statement

Creating social video content involves multiple disconnected tasks: choosing a topic, writing a script, planning scenes, generating visuals and voice, adding captions, assembling the video, checking quality, and publishing it. Repeating these tasks manually is slow and difficult to scale.

IdeaFeed AI brings these steps into one orchestrated workflow with persistent job status, failure recovery, user approval, and a path to learn from real performance data.

## 3. Goals

### MVP goals
1. Provide a backend API that accepts a topic, script, or image-based brief.
2. Generate a script, hooks, and a structured scene plan.
3. Generate or process visuals and narration through replaceable provider adapters.
4. Compose an MP4 with optional subtitles and background music.
5. Track each generation as a persistent asynchronous job.
6. Validate the result and expose quality-check findings.
7. Require approval before publishing.
8. Publish to Qoneqt through a verified, authorized integration; if unavailable, support an explicit manual/approved handoff without pretending it was published automatically.
9. Store project history and available analytics.
10. Make model use, failures, estimated cost, and progress observable.

### Out of scope for the first MVP
- Guaranteed virality or guaranteed view counts.
- Fabricated or simulated Qoneqt analytics presented as real.
- Unofficial scraping, credential sharing, or bypassing platform controls.
- Fully automatic public publishing without an authorized account and explicit approval.
- Complex multi-user enterprise billing.
- Full timeline-based video editing comparable to a professional editor.
- Training proprietary foundation models.
- Real-time collaboration.
- Automatic scheduling unless the authorized Qoneqt integration supports it.

## 4. Target Users

- **Creator/operator:** submits topics and scripts, configures a video, reviews outputs, and approves publication.
- **Publisher/admin:** manages the designated Qoneqt account/integration and publishes approved videos.
- **Demo/evaluator:** follows a complete, observable workflow and verifies the final output.

For the MVP, the creator and publisher may be the same person, but publishing permissions must be enforced in the backend.

## 5. Core User Journey

1. User submits a topic/prompt, their own script, and optionally reference images.
2. Backend validates the request and creates a project and generation job.
3. AI analyzes the brief and creates hooks, a script, and a structured storyboard.
4. User may edit the script/storyboard before rendering.
5. Backend generates narration, visuals, and captions according to selected settings.
6. Media pipeline assembles the final MP4.
7. Quality checks validate technical properties and flag likely content issues.
8. User previews the result and can edit or regenerate a scene.
9. User approves the final version.
10. Publisher posts through the authorized Qoneqt integration, or follows a clearly labelled manual handoff if the integration is unavailable.
11. Backend records the publish outcome and fetches analytics only if supported.
12. AI performance insights may recommend follow-up topics based on real available data.

## 6. Functional Requirements

Priority key:
- **P0 — Required for the core demo**
- **P1 — High-value enhancement**
- **P2 — Later enhancement / dependent on platform access**

### 6.1 Project and input management

- **P0** Create a project from a topic, prompt, trend idea, or user-provided script.
- **P0** Accept optional reference image uploads.
- **P0** Support Hindi, English, and Hinglish inputs/outputs where selected providers support them.
- **P0** Configure duration, aspect ratio, theme, effort mode, and captions.
- **P0** Save all settings and generated versions to project history.
- **P1** Allow script editing and saving before rendering.
- **P1** Allow project duplication and reuse of settings.
- **P1** Provide searchable project/video library.

### 6.2 AI brief, scripting, and storyboard

- **P0** Produce a concise content brief from the user input.
- **P0** Generate a hook, narration script, and scene-by-scene storyboard.
- **P1** Generate up to three hook alternatives.
- **P1** Allow individual scene prompt editing and regeneration.
- **P1** Provide a source-backed trend brief when supported by permitted data sources.
- **P1** Flag factual claims that may require verification; do not present unverified claims as verified facts.
- **P2** Learn preferred formats from the user's historical performance data where sufficient data is available.

Each storyboard scene should contain at minimum:
- Scene number.
- Visual prompt/description.
- Narration segment.
- Target duration.
- Caption segment.
- Transition suggestion.
- Generation status.
- Provider/model metadata when available.

### 6.3 Generation settings

- **P0** Aspect ratio: 9:16, 16:9, and 1:1; allow custom dimensions only when the selected pipeline supports them.
- **P0** Duration presets: 15, 30, and 60 seconds; validate provider limits and final render duration.
- **P0** Themes: minimalist, cinematic, documentary, news, educational, business/corporate, vibrant, dark, and custom prompt.
- **P0** Effort modes:
  - **Medium:** one primary script/storyboard pass, standard generation, basic quality checks.
  - **Large:** additional hook/scene refinement and stronger validation.
  - **Max:** multiple candidates and additional refinement where budget/provider limits permit.
- **P0** Effort modes must have configurable limits; Max must never mean unlimited usage.
- **P1** Background music selection and volume.
- **P1** Thumbnail generation.
- **P1** Reusable brand kit with logo, colors, fonts, and caption presets.

### 6.4 Voice, transcription, and captions

- **P0** Integrate voice synthesis behind a provider adapter so providers can be changed without rewriting the workflow.
- **P0** Expose only voices/languages actually supported by the configured provider.
- **P0** Support Hindi and English; Hinglish should be tested for pronunciation quality before being advertised as fully supported.
- **P0** Generate speech audio and align captions using provider timestamps or transcription/alignment tooling where available.
- **P0** Captions can be enabled or disabled.
- **P0** Caption settings: color, size, position, background/transparency, and outline where supported.
- **P0** Support subtitle burn-in for the final video.
- **P1** Export SRT/VTT subtitle files.
- **P1** Preview voice samples before generation.
- **P1** Offer tone/speed/volume controls where supported.
- **P1** Provide manual transcript correction.
- **P2** Advanced word-by-word highlighting and a pronunciation dictionary.

### 6.5 Media composition

- **P0** Compose generated visuals, narration, captions, and optional music into an MP4.
- **P0** Normalize dimensions, frame rate, audio sample rate, and encoding to the selected export profile.
- **P0** Keep temporary files scoped to a job and clean them up according to retention settings.
- **P0** Validate output file existence, duration, dimensions, audio stream, and video stream.
- **P1** Regenerate an individual scene without rerunning unaffected completed scenes.
- **P1** Add transitions and configurable intro/outro.
- **P1** Generate multiple final variants from one project.
- **P1** Create a thumbnail/cover image.

### 6.6 Quality assurance and recovery

- **P0** Provide technical checks for missing media, zero-byte files, invalid duration/dimensions, absent audio/video streams, and caption file/render failures.
- **P0** Detect failed provider calls and persist a clear error state.
- **P0** Retry transient failures with a bounded retry policy.
- **P0** Avoid duplicate jobs and duplicate publication attempts using idempotency keys.
- **P0** Persist completed stage outputs so a failed later stage can resume from the last successful stage.
- **P1** Check for blank/black frames, caption overflow, excessive silence, and scene/script mismatch where practical.
- **P1** Provide repair suggestions and allow the user to regenerate selected scenes.
- **P1** Expose stage-level logs, duration, and error messages without leaking secrets.
- **P1** Add a quality report before approval.

### 6.7 Review, approval, and publishing

- **P0** Workflow states: draft, queued, processing, needs_review, approved, publishing, published, publish_failed, cancelled.
- **P0** Only approved final versions can be sent to the publishing adapter.
- **P0** Store approval identity and timestamp.
- **P0** Integrate Qoneqt only after official API/SDK/access requirements have been confirmed.
- **P0** Do not claim successful publishing until the platform confirms success.
- **P0** If API access is unavailable, provide a clearly labelled manual export/handoff path and record that it is not an automatic publish.
- **P1** Designated account connection status and permission validation.
- **P1** Publish title, description, hashtags, and thumbnail when supported.
- **P1** Retry failed publishing safely without creating duplicate posts.
- **P2** Scheduling, if supported by the authorized integration.
- **P2** Multi-account management and team-level approvals.

### 6.8 Analytics and AI recommendations

- **P0** Dashboard shows counts for projects, generation jobs, successful renders, failed jobs, and publish states based on internal records.
- **P0** Clearly distinguish internal workflow metrics from Qoneqt viewership metrics.
- **P1** Fetch views, likes, comments, shares, or other metrics only if Qoneqt exposes them through an authorized source.
- **P1** Show per-video performance over time when real data is available.
- **P1** AI summarizes observed patterns and suggests follow-up topics; recommendations must not imply guaranteed reach.
- **P1** Trend dashboard includes source, retrieval time, and explanation for each recommendation when supported.
- **P2** A/B comparisons for hooks/thumbnails with adequate data.
- **P2** Content calendar and scheduled publishing.

### 6.9 Usage, cost, and security

- **P0** Store provider keys only in server-side environment secrets/secret management.
- **P0** Never return API keys or raw secrets to the frontend or logs.
- **P0** Enforce file type, file size, MIME, and upload limits.
- **P0** Validate and sanitize user inputs and uploaded filenames.
- **P0** Apply request limits and authenticated access to project/publishing endpoints.
- **P0** Maintain provider usage/cost metadata where available.
- **P0** Configure per-job timeout, retry count, maximum duration, and effort-mode limits.
- **P1** Estimate cost before generation where provider pricing/usage data allows.
- **P1** Add configurable usage budget and warning thresholds.
- **P1** Add deletion/retention controls for uploaded and generated media.
- **P1** Audit generation, approval, and publish actions.

---

## 7. Backend-First Technical Architecture

### 7.1 Architecture principles

1. Design and test the backend API and job lifecycle before building the full frontend.
2. Use asynchronous jobs for generation; do not hold an HTTP request open while a long video is being rendered.
3. Keep providers replaceable behind interfaces/adapters.
4. Persist job state and stage outputs so work can recover after process restarts.
5. Treat video generation and publishing as separate workflows.
6. Make the core pipeline demonstrable even when optional providers are unavailable.
7. Never fake a provider result, a successful publish, or external analytics.

### 7.2 Suggested components

- **API service:** Node.js + Express (or the existing Node framework if the project already has one).
- **Database:** MongoDB for users/projects/jobs/assets/publish records; use existing database if already established.
- **Worker:** background worker process for orchestration and provider calls.
- **Media pipeline:** FFmpeg for composition, transcoding, audio mixing, and subtitle burn-in.
- **AI orchestration:** LLM adapter for script/storyboard generation.
- **Visual generation adapter:** text-to-video, image-to-video, or permitted fallback provider.
- **TTS adapter:** speech generation provider with replaceable voice engines.
- **Transcription/alignment adapter:** speech recognition or provider timestamps for subtitles.
- **File storage:** object storage in production; local temporary storage only for development.
- **Frontend:** React + Vite dashboard after backend contracts and core flow are tested.

**Important:** exact provider selection depends on current API access, supported languages, pricing, quotas, and licensing. The system must not assume that a service is free or that every provider supports every option.

### 7.3 High-level architecture

```text
React UI (later)
    |
    v
Node.js REST API
    |
    +---- MongoDB (projects, jobs, assets, approvals, publishing, metrics)
    |
    +---- Queue / persistent job scheduler
                |
                v
          Background Worker
                |
        +-------+---------+-----------+
        |                 |           |
        v                 v           v
   LLM Adapter       Media Adapters  TTS/ASR Adapters
   Script/Scenes     Video/Images    Voice/Transcription
        |                 |           |
        +-----------------+-----------+
                          |
                          v
                     FFmpeg Pipeline
                          |
                          v
                  Storage: final MP4
                          |
                          v
                    Quality Gate
                          |
                          v
                  Approval + Publisher
                          |
                          v
                Qoneqt (authorized path)
                          |
                          v
                 Analytics (if available)
```

For a robust deployment, run API and worker separately. If a queue is not available initially, implement a persistent database-backed job runner rather than relying only on in-memory timers.

---

## 8. Backend API Contract (Proposed)

Use versioned routes under `/api/v1`. Exact implementation can be adjusted to the existing codebase.

### Projects
- `POST /api/v1/projects` — create project from topic/script and settings.
- `GET /api/v1/projects` — list projects with pagination and filters.
- `GET /api/v1/projects/:projectId` — get project, settings, storyboard, and latest status.
- `PATCH /api/v1/projects/:projectId` — edit script, settings, or metadata.
- `DELETE /api/v1/projects/:projectId` — delete project and associated assets according to retention rules.

### Uploads and assets
- `POST /api/v1/assets/upload-url` — request a secure upload URL where object storage supports it.
- `POST /api/v1/projects/:projectId/assets` — register a validated uploaded image/audio asset.
- `GET /api/v1/projects/:projectId/assets` — list project assets.
- `DELETE /api/v1/assets/:assetId` — remove an asset.

### AI planning
- `POST /api/v1/projects/:projectId/plan` — generate content brief, hooks, script, and storyboard.
- `PATCH /api/v1/projects/:projectId/storyboard` — edit scene plan.
- `POST /api/v1/projects/:projectId/scenes/:sceneId/regenerate` — regenerate a selected scene.
- `POST /api/v1/projects/:projectId/script/variants` — generate alternative hooks/scripts.

### Generation jobs
- `POST /api/v1/projects/:projectId/generations` — queue a render job; accept `Idempotency-Key`.
- `GET /api/v1/jobs/:jobId` — retrieve status, progress, current stage, and safe errors.
- `GET /api/v1/jobs/:jobId/events` — progress stream using SSE if implemented.
- `POST /api/v1/jobs/:jobId/cancel` — request cancellation.
- `POST /api/v1/jobs/:jobId/retry` — retry a failed job where retry is safe.

### Review and export
- `GET /api/v1/projects/:projectId/quality-report` — get quality checks.
- `GET /api/v1/projects/:projectId/preview` — get authorized preview URL/metadata.
- `POST /api/v1/projects/:projectId/approve` — approve a specific final version.
- `POST /api/v1/projects/:projectId/exports` — create downloadable MP4/subtitle export.

### Publishing
- `GET /api/v1/publishing/account` — account connection and capability status.
- `POST /api/v1/projects/:projectId/publish` — queue publish for an approved version.
- `GET /api/v1/publishing/:publishJobId` — publish status/result.
- `POST /api/v1/publishing/:publishJobId/retry` — safe retry after failure.
- `POST /api/v1/projects/:projectId/manual-publish-handoff` — generate a manual handoff/export package if official integration is unavailable.

### Trends and analytics
- `GET /api/v1/trends` — retrieve cached topic suggestions with sources and timestamps.
- `POST /api/v1/trends/analyze` — analyze a topic and produce a video brief.
- `GET /api/v1/analytics/overview` — internal project/job/publish metrics.
- `GET /api/v1/projects/:projectId/analytics` — platform metrics only if supported.
- `POST /api/v1/projects/:projectId/insights` — generate recommendations from available data.

### Health and configuration
- `GET /api/v1/health` — liveness.
- `GET /api/v1/ready` — readiness, database and required dependencies.
- `GET /api/v1/providers/status` — configured provider capabilities without exposing secrets.

**API rules**
- Validate every request with a schema.
- Return a consistent error format: `code`, `message`, optional safe `details`, and `requestId`.
- Use HTTP 202 for queued long-running work.
- Paginate list endpoints.
- Enforce authorization and ownership on every project, asset, job, approval, and publish operation.
- Keep external provider errors safe and useful without leaking secrets.
- Use idempotency for expensive generation and publishing operations.

---

## 9. Data Model (Initial)

### Project
- `_id`
- `ownerId`
- `title`
- `inputType`: `topic | script | image | mixed`
- `topic`
- `sourceScript`
- `language`
- `settings`: duration, aspect ratio, theme, effort, captions, voice, music
- `script`
- `hooks[]`
- `storyboard[]`
- `status`
- `createdAt`
- `updatedAt`

### GenerationJob
- `_id`
- `projectId`
- `ownerId`
- `status`
- `currentStage`
- `progressPercent`
- `stageResults[]`
- `attemptCount`
- `idempotencyKey`
- `providerMetadata[]`
- `estimatedCost`
- `actualCost`
- `errorCode`
- `safeErrorMessage`
- `createdAt`
- `startedAt`
- `completedAt`

### Asset
- `_id`
- `projectId`
- `ownerId`
- `type`: `reference_image | generated_image | generated_video | voice_audio | music | subtitles | thumbnail | final_video`
- `storageKey`
- `mimeType`
- `sizeBytes`
- `durationSeconds`
- `width`
- `height`
- `checksum`
- `createdAt`
- `expiresAt`

### Approval
- `_id`
- `projectId`
- `versionId`
- `approverId`
- `decision`: `approved | rejected`
- `notes`
- `createdAt`

### PublishJob
- `_id`
- `projectId`
- `versionId`
- `destination`: `qoneqt`
- `accountId`
- `status`
- `externalPostId` (if returned)
- `externalUrl` (if returned)
- `attemptCount`
- `errorCode`
- `safeErrorMessage`
- `publishedAt`
- `createdAt`

### AnalyticsSnapshot
- `_id`
- `projectId`
- `publishJobId`
- `source`
- `capturedAt`
- `views`
- `likes`
- `comments`
- `shares`
- `rawMetrics` (only necessary permitted fields)

### TrendItem
- `_id`
- `topic`
- `summary`
- `sourceName`
- `sourceUrl`
- `publishedAt`
- `retrievedAt`
- `relevanceScore`
- `suggestedHooks[]`
- `expiresAt`

Do not store sensitive provider credentials in these collections. Use environment secrets/secret management.

---

## 10. Job Lifecycle and State Transitions

Generation lifecycle:

`queued → planning → generating_voice → generating_visuals → composing → quality_check → needs_review → approved`

Possible terminal or recovery states:
- `failed`
- `cancelled`
- `retrying`

Publishing lifecycle:

`pending_approval → approved → publishing → published`

Failure path:

`publishing → publish_failed → retrying → published | publish_failed`

Rules:
- A job can enter `needs_review` only after a final artifact exists and required quality checks have completed.
- A project cannot publish a version without approval for that exact version.
- Editing the final output after approval invalidates the approval and requires re-approval.
- Repeated requests with the same idempotency key must not create duplicate generation jobs or duplicate posts.
- The API must never label a manual handoff as `published`.

---

## 11. Non-Functional Requirements

### Reliability
- Persistent status survives API/worker restarts.
- Every generation stage records start/end time and outcome.
- Retry transient failures with bounded exponential backoff.
- Support resuming from completed stages where output remains valid.
- Do not block API requests while rendering videos.

### Performance
- Project creation and job enqueueing should return promptly.
- Long-running tasks report progress.
- Use pagination for history and analytics.
- Cache trend results and avoid repeatedly calling expensive sources.

### Security and privacy
- Authentication required for non-public endpoints.
- Verify project ownership and publisher permissions.
- Secrets stay server-side.
- Validate uploads and protect against oversized/malicious files.
- Use short-lived signed URLs for private media where supported.
- Avoid logging raw scripts or personal content unless needed for debugging.
- Provide configurable media retention and deletion.

### Observability
- Structured logs with `requestId`, `projectId`, and `jobId`.
- Track provider latency, failures, retries, and estimated/actual usage.
- Health/readiness endpoints.
- Alerts or visible warnings for missing required provider configuration.

### Accessibility and usability
- Keep progress and failure states understandable.
- Never show fabricated progress or fake analytics.
- Explain when a feature is unavailable due to provider/account limitations.

---

## 12. Backend-First Implementation Plan

Do not begin with the complete UI. Build and validate the backend in the following order.

### Phase 0 — Repository and provider feasibility
1. Inspect the existing repository and preserve working code.
2. Confirm Node version, framework, database, storage, deployment environment, and current TTS/video provider.
3. Verify credentials, quotas, language support, output formats, and API terms for each chosen provider.
4. Confirm Qoneqt publishing requirements with the Qoneqt team.
5. Write a `.env.example` containing names only, never real credentials.

**Exit criteria:** the chosen providers can perform a minimal test, or unavailable providers have a clearly documented fallback.

### Phase 1 — API foundation
1. Set up environment configuration and centralized error handling.
2. Add database connection and health/readiness endpoints.
3. Add authentication/authorization.
4. Create project, asset, and job schemas with indexes.
5. Implement project CRUD and request validation.
6. Add API tests.

**Exit criteria:** project creation, listing, retrieval, update, and authorization tests pass.

### Phase 2 — Persistent job orchestration
1. Implement a persistent queue/job runner.
2. Add generation states, progress, cancellation, retry and idempotency.
3. Add stage-level logs and bounded timeouts.
4. Build a mock provider for deterministic tests only; label mock outputs clearly and never use them as real demo generation.

**Exit criteria:** a job survives process restart and resumes or fails clearly without duplicate execution.

### Phase 3 — AI planning
1. Implement LLM adapter.
2. Validate structured script/storyboard output.
3. Add hook alternatives and language settings.
4. Persist editable scripts and scenes.

**Exit criteria:** a sample topic consistently produces a valid script and storyboard matching the selected duration and language constraints.

### Phase 4 — Real media generation
1. Implement visual-generation adapter.
2. Implement TTS adapter and test Hindi/English output quality.
3. Add transcription/alignment adapter.
4. Store intermediate assets and metadata.
5. Add individual-scene retry where supported.

**Exit criteria:** a real topic produces actual narration and visual assets through configured providers.

### Phase 5 — Composition and quality gate
1. Compose video using FFmpeg.
2. Apply dimensions, timing, captions, and audio mix.
3. Validate MP4 streams, dimensions, duration, and file size.
4. Generate quality report.
5. Implement retry/resume for failed stages.

**Exit criteria:** final MP4 plays correctly and required quality checks pass.

### Phase 6 — Approval and Qoneqt publishing
1. Add approval records bound to exact final version.
2. Implement publisher interface.
3. Integrate only the official/authorized Qoneqt route once confirmed.
4. Test successful, failed, and duplicate publish attempts.
5. If API access is unavailable, implement honest manual handoff.

**Exit criteria:** the system either verifies a real Qoneqt post or explicitly records a manual handoff without misrepresenting it.

### Phase 7 — Analytics and trends
1. Add internal dashboard aggregation.
2. Connect only authorized, supported trend sources.
3. Store source attribution and retrieval timestamps.
4. Add Qoneqt analytics only if accessible.
5. Generate evidence-based recommendations from available data.

**Exit criteria:** internal metrics are accurate; external metrics are sourced and labelled.

### Phase 8 — Frontend integration
Only after the API contracts and core backend workflow are tested:
1. Build Create Video and project library.
2. Add storyboard editor and job progress.
3. Add preview, quality report, approval and publish screens.
4. Add trends, analytics and settings.
5. Connect every screen to real endpoints.

**Exit criteria:** no critical screen relies on hard-coded fake data in the demo.

### Phase 9 — Deployment and demo readiness
1. Deploy API, worker, database, and storage.
2. Configure secrets and CORS.
3. Test health/readiness and restart recovery.
4. Run a full end-to-end generation.
5. Publish at least one real generated video if authorized access is available.
6. Record a backup demo in case a third-party provider is temporarily unavailable.

---

## 13. Testing Plan

### Unit tests
- Request validation and settings constraints.
- Storyboard schema validation.
- Job state transition rules.
- Idempotency and retry policy.
- Approval/version rules.
- Cost/usage limit checks.

### Integration tests
- Database persistence and indexes.
- LLM provider response parsing.
- TTS and visual provider adapters.
- FFmpeg composition and subtitle rendering.
- Upload validation and storage access.
- Publisher adapter success/failure handling.

### End-to-end acceptance tests
1. Create a project with a topic.
2. Generate and edit a script/storyboard.
3. Queue a video job and poll progress.
4. Confirm real voice and visuals are generated.
5. Verify final MP4 duration, dimensions, audio, and video streams.
6. Confirm quality report is available.
7. Approve the exact final version.
8. Publish through authorized Qoneqt integration or use the clearly labelled manual handoff.
9. Confirm dashboard counts reflect actual internal records.
10. Confirm no external view count is displayed unless it was retrieved from a real source.

---

## 14. MVP Acceptance Criteria

The MVP is ready for demonstration when:

- [ ] Backend project APIs and validation work.
- [ ] Generation runs asynchronously and status persists in the database.
- [ ] A topic or uploaded script generates a structured script and storyboard.
- [ ] At least one configured real provider generates narration.
- [ ] At least one configured real provider generates or processes actual visuals/video.
- [ ] FFmpeg produces a playable MP4 with selected aspect ratio.
- [ ] Captions can be enabled/disabled and styled.
- [ ] Technical quality checks run and produce a report.
- [ ] The user can preview and approve the exact final version.
- [ ] Publishing is either verified through an authorized Qoneqt integration or honestly offered as a manual handoff.
- [ ] At least one generated video is published to Qoneqt Global Feed for the challenge, if the required access is provided.
- [ ] Internal dashboard counts match stored records.
- [ ] Secrets are not exposed to the frontend or logs.
- [ ] README, `.env.example`, setup instructions, and a demo flow are available.

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Free API quota is too small | Verify quota before integration; provide provider adapters and budget limits |
| TTS sounds unnatural | Test Hindi/English samples early; allow provider replacement and voice preview |
| Video generation is slow or fails | Async jobs, bounded retries, persisted stage outputs, scene-level regeneration |
| Qoneqt API access is unavailable | Ask the platform team early; implement manual handoff without faking publication |
| Analytics are inaccessible | Display internal metrics only and clearly mark external metrics unavailable |
| Model output is malformed | Enforce structured schemas, validation, and bounded repair attempts |
| Deployment worker restarts | Persist job state and outputs; resume from last successful stage |
| Generation costs spike | Estimate usage, enforce budgets, and require confirmation for Max mode |
| User uploads unsafe or oversized files | Validate type, size, content metadata, and access permissions |
| Scope becomes too large | Lock P0 requirements first; defer P1/P2 features until end-to-end flow works |

---

## 16. Decisions Required Before Implementation

Resolve these early rather than guessing:

1. Existing repository and backend framework.
2. MongoDB or the already-used database.
3. Actual visual/video generation provider and its confirmed quota.
4. TTS provider with acceptable Hindi and English sample quality.
5. Storage provider and retention requirements.
6. Authentication method and designated publisher identity.
7. Official Qoneqt API/SDK or approved publishing workflow.
8. Whether Qoneqt exposes post-level analytics.
9. Deployment host for the API and persistent worker.

## 17. Final Product Principle

**Build a reliable backend pipeline first. Add the frontend only after a real video can travel through the backend from input to a validated final artifact.**

The strongest MVP is not the one with the most toggles. It is the one that creates a real video, survives failures, keeps a human in control of publishing, and can demonstrate its results honestly.

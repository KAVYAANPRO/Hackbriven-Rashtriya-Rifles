# frontend.md — IdeaFeed AI
## Frontend MVP Specification for the Qoneqt × CTRL FREAK Challenge

**Document status:** MVP frontend specification  
**Product name:** IdeaFeed AI (working title)  
**Frontend stack:** React + Vite  
**Primary platform:** Web dashboard  
**Backend dependency:** `/api/v1` REST API defined in `PRD.md`

---

## 1. Frontend Objective

The frontend is the operator interface for the IdeaFeed AI backend pipeline.

It must let a creator move through the complete product workflow:

**Idea / Script → AI Plan → Storyboard Review → Generation → Quality Review → Approval → Publish / Manual Handoff → Analytics**

The frontend must reflect real backend state. It must not simulate successful generation, publishing, analytics, provider availability, or job progress.

The UI should optimize for:
- A clear end-to-end creation flow.
- Minimal confusion during long-running generation jobs.
- Human review before publishing.
- Fast recovery from failures.
- Visibility into provider limitations, generation effort, cost, and quality.
- A strong challenge/demo experience without relying on fake data.

---

## 2. Frontend Principles

1. **Backend state is the source of truth.**
2. **Long-running operations are asynchronous.** Never freeze a page waiting for generation.
3. **Every important state must have an explicit UI:** loading, empty, queued, processing, failed, review required, approved, publishing, published, cancelled, unavailable.
4. **Do not fabricate progress.** Display backend `progressPercent`, `currentStage`, and events only.
5. **Do not fabricate analytics.** External metrics appear only when returned by an authorized source.
6. **Do not expose provider secrets or API keys.**
7. **Approval is version-specific.** Any edit that invalidates backend approval must immediately be reflected in the UI.
8. **Publishing and generation are separate workflows.**
9. **Unavailable integrations should degrade honestly.** If Qoneqt automatic publishing is unavailable, show Manual Handoff rather than a fake Publish success.
10. **P0 flow comes before dashboard polish.**

---

## 3. MVP Information Architecture

### Primary navigation

Desktop sidebar:

- Dashboard
- Create Video
- Projects
- Trends
- Analytics
- Settings

Optional bottom area:
- Provider Status
- Qoneqt Connection
- User/Profile

For the first P0 implementation, only these must be fully functional:

- Dashboard
- Create Video
- Projects
- Project Workspace
- Generation Progress
- Review / Quality
- Approval
- Publish / Manual Handoff

Trends, richer analytics, brand kit, and advanced settings can remain P1.

---

## 4. Route Map

```text
/
├── /dashboard
├── /create
├── /projects
│   └── /projects/:projectId
│       ├── /plan
│       ├── /storyboard
│       ├── /generate
│       ├── /review
│       ├── /publish
│       └── /analytics
├── /jobs/:jobId
├── /trends
├── /analytics
└── /settings
    ├── /providers
    └── /publishing
```

Recommended behavior:

- `/` redirects to `/dashboard`.
- Project sub-routes use the project workspace shell.
- A project may only access steps valid for its current state.
- Direct navigation to a future step should redirect to the latest valid step or show a clear state message.
- Refreshing a processing page must restore the job from backend state rather than restarting generation.

---

## 5. Global Application Shell

### 5.1 Desktop layout

Use:
- Left sidebar navigation.
- Top application bar.
- Main content area.
- Optional right-side contextual panel for settings/details on complex editor screens.

Top bar may contain:
- Current project title when inside a project.
- Backend/provider warning indicator.
- Qoneqt connection indicator.
- User menu.

### 5.2 Mobile / narrow layouts

The MVP is primarily a dashboard, but core actions should remain usable on tablet/mobile:
- Sidebar collapses to drawer.
- Storyboard cards stack vertically.
- Settings panels become drawers or accordions.
- Video preview maintains selected aspect ratio.
- Primary action remains sticky when useful.

### 5.3 Global status surfaces

Use:
- Toasts for short success/failure feedback.
- Inline errors for form fields.
- Persistent banners for provider/account outages.
- Confirmation dialogs for destructive or expensive actions.
- Skeletons for initial data loading.
- Progress UI only when real backend progress exists.

---

## 6. Core User Flow

### Step 1 — Create Project

User enters:
- Topic / prompt, or
- Existing script.
- Optional reference image(s).

User configures:
- Language.
- Duration.
- Aspect ratio.
- Theme.
- Effort mode.
- Captions on/off.

Submit creates a project.

**API**
- `POST /api/v1/projects`
- Upload flow as required:
  - `POST /api/v1/assets/upload-url`
  - `POST /api/v1/projects/:projectId/assets`

On success:
- Navigate to `/projects/:projectId/plan`.

### Step 2 — Generate AI Plan

The frontend requests:
- Content brief.
- Hook.
- Script.
- Storyboard.

**API**
- `POST /api/v1/projects/:projectId/plan`

The UI must distinguish:
- Planning request queued/processing.
- Planning complete.
- Planning failed.

When complete, show editable output.

### Step 3 — Review Script and Storyboard

User can:
- Edit script.
- Edit scene visual prompts.
- Edit narration/captions where backend contract permits.
- Review target scene durations.
- Generate hook/script alternatives if implemented.
- Save changes.
- Regenerate an individual scene when supported.

**API**
- `PATCH /api/v1/projects/:projectId`
- `PATCH /api/v1/projects/:projectId/storyboard`
- `POST /api/v1/projects/:projectId/script/variants`
- `POST /api/v1/projects/:projectId/scenes/:sceneId/regenerate`

### Step 4 — Generate Video

Before queueing generation, show a compact generation summary:
- Duration.
- Aspect ratio.
- Language.
- Theme.
- Effort.
- Captions.
- Voice.
- Optional estimated cost if backend provides it.

For expensive/Max generation, require explicit confirmation if backend policy requires it.

**API**
- `POST /api/v1/projects/:projectId/generations`

Send an `Idempotency-Key`.

Navigate to:
- `/jobs/:jobId` or project generation route.

### Step 5 — Track Generation

Display real stage progression:

```text
queued
planning
generating_voice
generating_visuals
composing
quality_check
needs_review
```

Display:
- Overall progress percentage.
- Current stage.
- Completed stages.
- Elapsed time if derivable from timestamps.
- Safe backend error message.
- Cancel button when allowed.
- Retry button when failed and safe.
- Cost/usage metadata when available.

**API**
- `GET /api/v1/jobs/:jobId`
- `GET /api/v1/jobs/:jobId/events` if SSE exists.
- `POST /api/v1/jobs/:jobId/cancel`
- `POST /api/v1/jobs/:jobId/retry`

If SSE is unavailable, poll with bounded frequency.

Recommended polling:
- Active generation: every 2–4 seconds.
- Stop polling in terminal/review states.
- Pause or reduce polling when tab is hidden if appropriate.

Never animate fake percentage increments between backend updates.

### Step 6 — Review Final Video

Once the project reaches `needs_review`, show:
- Video preview.
- Version identifier.
- Video metadata.
- Quality report.
- Technical warnings.
- Scene list.
- Regenerate scene actions where supported.
- Export/download action.
- Approve action.

**API**
- `GET /api/v1/projects/:projectId/preview`
- `GET /api/v1/projects/:projectId/quality-report`
- `POST /api/v1/projects/:projectId/exports`

If regeneration changes the final version:
- Refresh preview/version.
- Remove any stale approval state.

### Step 7 — Approve

Approval must clearly state that the exact displayed version is being approved.

**API**
- `POST /api/v1/projects/:projectId/approve`

After success:
- Show Approved badge.
- Record/display approval time when returned.
- Enable publishing actions.

### Step 8 — Publish

First fetch publishing capabilities.

**API**
- `GET /api/v1/publishing/account`

If automatic Qoneqt publishing is supported:
- Show publish metadata fields supported by the backend/platform.
- Submit publish.
- Track publish status.

**API**
- `POST /api/v1/projects/:projectId/publish`
- `GET /api/v1/publishing/:publishJobId`
- `POST /api/v1/publishing/:publishJobId/retry`

If automatic publishing is unavailable:
- Show a clearly labelled **Manual Handoff** path.
- Explain that the video has not been automatically published.
- Generate/export the handoff package.

**API**
- `POST /api/v1/projects/:projectId/manual-publish-handoff`

---

## 7. Screen Specifications

## 7.1 Dashboard

### Purpose
Give the operator an accurate summary of current work and quick access to creation.

### P0 content

Header:
- “Dashboard”
- Primary CTA: `Create Video`

Metric cards:
- Projects.
- Generation jobs.
- Successful renders.
- Failed jobs.
- Published.
- Publish failed / awaiting publish.

These are internal workflow metrics only.

Recent projects:
- Thumbnail if available.
- Project title.
- Input type.
- Updated time.
- Status.
- Progress if active.
- Open project action.

Active jobs:
- Project.
- Current stage.
- Real progress.
- Started time.
- View job.

### API
- `GET /api/v1/analytics/overview`
- `GET /api/v1/projects?sort=updatedAt&limit=...`

### Empty state
“No projects yet” + `Create your first video`.

---

## 7.2 Create Video

### Page structure

#### A. Input

Use tabs or segmented control:
- Topic / Prompt
- Script

Topic field:
- Multiline textarea.
- Required when input type is topic.

Script field:
- Larger editor textarea.
- Required when input type is script.

Optional reference images:
- Drag/drop area.
- File picker.
- Preview thumbnails.
- Remove action.
- Upload progress.
- Client-side file checks before upload.

Do not assume accepted MIME types/sizes; consume limits from configuration if exposed or keep UI validation synchronized with backend rules.

#### B. Video settings

Fields:
- Language: English / Hindi / Hinglish only when backend/provider capability allows.
- Duration: 15 / 30 / 60 seconds.
- Aspect ratio: 9:16 / 16:9 / 1:1.
- Theme:
  - Minimalist
  - Cinematic
  - Documentary
  - News
  - Educational
  - Business / Corporate
  - Vibrant
  - Dark
  - Custom
- Custom theme prompt when Custom is selected.
- Effort:
  - Medium
  - Large
  - Max
- Captions toggle.

Optional P1:
- Voice.
- Background music.
- Caption styling.
- Brand kit.

#### C. Effort explanation

Each effort option should communicate that it changes generation/refinement effort, not guaranteed output quality.

Example UI descriptions:
- Medium — Standard generation and basic validation.
- Large — Additional refinement and stronger validation.
- Max — Multiple candidates/refinement within configured limits.

Never describe Max as unlimited.

#### D. Submit

Primary CTA:
`Create & Plan`

States:
- Disabled when invalid.
- Loading while creating project.
- Uploading state if assets are still being registered.
- Error with safe retry.

---

## 7.3 Project Workspace

Use a shared project shell.

Header:
- Project title.
- Status badge.
- Last updated.
- Optional overflow menu.

Step navigation:
1. Brief
2. Storyboard
3. Generate
4. Review
5. Publish

Completed steps show a check.
Current step is highlighted.
Future invalid steps are disabled.

Project-level actions:
- Rename.
- Duplicate (P1).
- Delete.
- Back to projects.

---

## 7.4 Brief / Script Screen

### Content brief card
Show:
- Topic summary.
- Audience/angle only if backend returns it.
- Language.
- Target duration.
- Theme.

### Hook section
P0:
- Selected hook.

P1:
- Up to three alternatives.
- Select hook.
- Generate alternatives.

### Script editor
- Editable textarea/editor.
- Character count optional.
- Save state:
  - Unsaved.
  - Saving.
  - Saved.
  - Save failed.

Do not auto-save in a way that can silently overwrite server changes unless concurrency behavior is explicitly implemented.

Primary CTA:
`Continue to Storyboard`

---

## 7.5 Storyboard Editor

This is a key MVP screen.

### Scene card

Each scene displays:
- Scene number.
- Visual prompt/description.
- Narration segment.
- Caption segment.
- Target duration.
- Transition suggestion.
- Generation status.
- Provider/model metadata when available.

Actions:
- Edit.
- Save.
- Regenerate scene where valid.
- Retry scene after failure where valid.

Optional visual thumbnail:
- Show generated asset when available.
- Otherwise show a neutral placeholder, not fake generated imagery.

### Layout

Recommended desktop:
- Left/main: ordered scene cards.
- Right: generation settings summary.

Alternative:
- Card grid with expandable editor.

### Duration feedback

Show:
- Sum of target scene durations.
- Selected total duration.

If scene total does not match selected duration, display backend validation or a local warning, but backend remains authoritative.

Primary CTA:
`Generate Video`

Before generation, show confirmation/summary.

---

## 7.6 Generation Progress Screen

### Header
“Generating your video”

Show project title and job ID in secondary/debug detail only if useful.

### Stage stepper

```text
Queued
Plan
Voice
Visuals
Compose
Quality Check
Review
```

Map backend stage names to friendly labels.

Each stage can be:
- Pending.
- Active.
- Complete.
- Failed.

### Progress panel
- Real percentage.
- Current stage.
- Stage message if backend provides one.
- Attempt count when retrying.
- Estimated/actual cost when available.

### Actions
- Cancel, if valid.
- Retry, after safe failure.
- Return to project.

### Failure UI

Display:
- Friendly failure heading.
- Backend safe error message.
- Failed stage.
- Retry if supported.
- Return to storyboard/settings if user action is required.

Never expose raw provider stack traces, tokens, secret values, or unsafe error payloads.

### Completion
When status becomes `needs_review`, automatically enable a prominent:
`Review Video`

Optional automatic navigation should not interrupt a user reading a failure/recovery message.

---

## 7.7 Review & Quality Screen

### Layout

Desktop recommendation:
- Left: video player.
- Right: approval/quality summary.
- Below: quality findings and scenes.

### Video player
Use authorized preview URL from backend.

Show:
- Aspect ratio.
- Duration.
- Resolution if returned.
- Version ID / version label.

### Quality summary
Statuses:
- Passed.
- Passed with warnings.
- Failed / action required.

Technical checks may include:
- Final file exists.
- Valid duration.
- Correct dimensions.
- Audio stream.
- Video stream.
- Caption render.

P1 checks may include:
- Blank/black frames.
- Caption overflow.
- Excessive silence.
- Scene/script mismatch.

Do not convert a warning into a hard failure unless backend defines it that way.

### Findings list
Each item:
- Severity.
- Check name.
- Safe explanation.
- Suggested repair if returned.
- Related scene if applicable.

### Actions
- Export.
- Regenerate scene.
- Approve version.

Approval button should display version context:
`Approve this version`

If quality state blocks approval according to backend rules, disable with explanation.

---

## 7.8 Publish Screen

### Precondition
Project version is approved.

If not approved:
- Show approval required.
- Link back to review.

### Connection/capability card
Display:
- Qoneqt connection state.
- Automatic publishing available/unavailable.
- Supported metadata/capabilities if returned.

### Automatic publishing flow

Fields only when supported:
- Title.
- Description.
- Hashtags.
- Thumbnail.

Primary CTA:
`Publish to Qoneqt`

After submission:
- Show publishing status.
- Prevent duplicate submit.
- Poll publish job or use supported events.
- On confirmed success, show:
  - Published state.
  - Published timestamp.
  - External post link only if returned.

Do not mark published before backend/platform confirmation.

### Publish failure
Show:
- Safe failure reason.
- Retry action if safe.
- No duplicate publication warning/behavior.

### Manual handoff flow
If automatic publishing is unavailable:
- Label section `Manual Handoff`.
- State that automatic publishing is not currently available.
- Allow handoff/export package creation.
- Show downloadable/exportable assets returned by backend.
- Never show status `published` solely because handoff was generated.

---

## 7.9 Projects Library

### P0 list
Each row/card:
- Thumbnail.
- Title.
- Input type.
- Language.
- Duration.
- Updated date.
- Current status.
- Active progress when relevant.

Filters:
- Status.
- Search by title if backend supports query/search.

Pagination required.

Actions:
- Open.
- Delete.

P1:
- Duplicate.
- More filters.
- Grid/list toggle.

### Status labels

Use consistent human-readable mapping:

```text
draft           → Draft
queued          → Queued
processing      → Processing
needs_review    → Needs review
approved        → Approved
publishing      → Publishing
published       → Published
publish_failed  → Publish failed
cancelled       → Cancelled
failed          → Failed
retrying        → Retrying
```

Backend may expose both project and job states. Keep their meanings distinct in frontend state models.

---

## 7.10 Trends — P1

### Purpose
Surface source-backed topic ideas only when authorized trend data exists.

Each trend item:
- Topic.
- Summary.
- Source name.
- Source link.
- Published/retrieved time.
- Suggested hooks.
- Relevance score if backend returns it.

Actions:
- `Use this topic`
- `Analyze`

### API
- `GET /api/v1/trends`
- `POST /api/v1/trends/analyze`

Never present an unsourced generated topic as a verified live trend.

---

## 7.11 Analytics — P0/P1

### P0
Internal workflow analytics:
- Projects.
- Jobs.
- Successful renders.
- Failed jobs.
- Approval/publish states.

### P1
When Qoneqt analytics are actually available:
- Views.
- Likes.
- Comments.
- Shares.
- Time series.
- AI observations/recommendations.

Clearly label source:
- `Internal workflow data`
- `Qoneqt analytics`

Show external metrics unavailable state when they cannot be fetched.

Never render placeholder view counts as if real.

### API
- `GET /api/v1/analytics/overview`
- `GET /api/v1/projects/:projectId/analytics`
- `POST /api/v1/projects/:projectId/insights`

---

## 7.12 Settings — P1

### Provider Status
Read-only frontend capability view.

Show configured capability, not credentials:
- LLM.
- Visual generation.
- TTS.
- Transcription/alignment.
- Publishing.

Possible state:
- Available.
- Degraded.
- Unavailable.
- Not configured.

**API**
- `GET /api/v1/providers/status`

### Publishing
Show Qoneqt account/capability state.

**API**
- `GET /api/v1/publishing/account`

Do not provide raw API key inputs unless the product later explicitly introduces a secure server-side credential-management workflow.

---

## 8. Component Architecture

Suggested React structure:

```text
src/
├── app/
│   ├── router/
│   ├── providers/
│   └── App.tsx
├── components/
│   ├── layout/
│   │   ├── AppShell
│   │   ├── Sidebar
│   │   ├── Topbar
│   │   └── ProjectShell
│   ├── common/
│   │   ├── Button
│   │   ├── Badge
│   │   ├── Modal
│   │   ├── ConfirmDialog
│   │   ├── EmptyState
│   │   ├── ErrorState
│   │   ├── Skeleton
│   │   ├── Pagination
│   │   └── FileUpload
│   ├── projects/
│   │   ├── ProjectCard
│   │   ├── ProjectStatusBadge
│   │   ├── ProjectStepNav
│   │   └── ProjectSettingsSummary
│   ├── storyboard/
│   │   ├── StoryboardEditor
│   │   ├── SceneCard
│   │   ├── SceneEditor
│   │   └── SceneStatus
│   ├── generation/
│   │   ├── GenerationSummary
│   │   ├── JobProgress
│   │   ├── StageStepper
│   │   └── JobError
│   ├── review/
│   │   ├── VideoPreview
│   │   ├── QualitySummary
│   │   ├── QualityFinding
│   │   └── ApprovalPanel
│   ├── publishing/
│   │   ├── PublishingCapability
│   │   ├── PublishForm
│   │   ├── PublishProgress
│   │   └── ManualHandoff
│   └── analytics/
│       ├── MetricCard
│       └── PerformancePanel
├── pages/
│   ├── DashboardPage
│   ├── CreateProjectPage
│   ├── ProjectsPage
│   ├── ProjectBriefPage
│   ├── StoryboardPage
│   ├── GenerationPage
│   ├── ReviewPage
│   ├── PublishPage
│   ├── TrendsPage
│   ├── AnalyticsPage
│   └── SettingsPage
├── api/
│   ├── client.ts
│   ├── projects.ts
│   ├── jobs.ts
│   ├── assets.ts
│   ├── publishing.ts
│   ├── analytics.ts
│   └── providers.ts
├── hooks/
│   ├── useProject
│   ├── useJob
│   ├── useJobEvents
│   └── usePublishingStatus
├── types/
├── utils/
└── styles/
```

This is a suggested organization, not a backend requirement.

---

## 9. Frontend Data Types

Frontend types should mirror API contracts rather than inventing separate business states.

Example conceptual types:

```ts
type ProjectStatus =
  | "draft"
  | "queued"
  | "processing"
  | "needs_review"
  | "approved"
  | "publishing"
  | "published"
  | "publish_failed"
  | "cancelled";

type GenerationStage =
  | "queued"
  | "planning"
  | "generating_voice"
  | "generating_visuals"
  | "composing"
  | "quality_check"
  | "needs_review";

type JobStatus =
  | "queued"
  | "processing"
  | "failed"
  | "cancelled"
  | "retrying"
  | "needs_review"
  | "approved";

type EffortMode = "medium" | "large" | "max";
type AspectRatio = "9:16" | "16:9" | "1:1";
type InputType = "topic" | "script" | "image" | "mixed";
```

Exact types must be updated to match implemented backend responses.

---

## 10. API Client Rules

Create one centralized API client.

Requirements:
- Base URL from environment configuration.
- Never hard-code production API URL into components.
- Include authentication credentials/token according to backend auth design.
- Parse the common backend error format:
  - `code`
  - `message`
  - `details`
  - `requestId`
- Handle `401` centrally.
- Handle `403` distinctly from `404`.
- Handle `429` with rate-limit feedback.
- Treat `202 Accepted` as queued work, not completion.
- Support request cancellation where useful.
- Never log auth tokens or sensitive request bodies in production.

Recommended environment variable:

```text
VITE_API_BASE_URL=
```

No provider secret belongs in `VITE_*` variables because Vite client environment values are exposed to the browser.

---

## 11. Async Job UX

Generation is the most important frontend state-management problem.

### Preferred approach
Use SSE from:

`GET /api/v1/jobs/:jobId/events`

when implemented.

### Fallback
Poll:

`GET /api/v1/jobs/:jobId`

### Client rules
- Initial job fetch immediately.
- Subscribe/poll only while job is active.
- Stop after terminal/review state.
- Reconnect after transient SSE disconnect.
- On browser refresh, recover by job ID.
- Never create a new generation job merely because a progress page remounted.
- Keep job creation mutation separate from job observation.
- Disable repeated generation submit while request is unresolved.
- Use backend idempotency support for expensive operations.

---

## 12. Forms and Validation

Frontend validation improves UX but does not replace backend validation.

Validate at minimum:
- Required input.
- Supported duration.
- Supported aspect ratio.
- Theme/custom-theme requirements.
- Reference image file type/size using known backend constraints.
- Required project/version state before actions.
- Publish metadata length only when limits are known.

When backend rejects a request:
- Preserve user-entered values.
- Show safe actionable message.
- Associate field errors when backend details permit.

Do not invent provider constraints. Unsupported options should come from provider/backend capability information where possible.

---

## 13. Upload UX

Reference image flow:

1. User selects file.
2. Frontend validates basic known constraints.
3. Request secure upload URL if required.
4. Upload directly to storage when backend architecture requires it.
5. Register asset against project.
6. Show successful thumbnail/asset state.

States:
- Selected.
- Uploading.
- Uploaded.
- Failed.
- Removing.

Do not treat successful storage upload as successful project asset registration until backend confirms it.

---

## 14. Approval Rules in UI

The UI must enforce the backend approval model.

- Publish action disabled before approval.
- Approval references the exact current version.
- Display current approved version when returned.
- If a scene or final output changes, refetch project approval state.
- Never preserve a green “Approved” UI solely in local state after editing.
- Re-approval is required when backend invalidates the previous approval.

---

## 15. Publishing Rules in UI

- Fetch capability before rendering an automatic-publish CTA.
- Disable publish while a publish request is active.
- Use backend publish job state.
- Do not infer success from an HTTP request merely being accepted.
- Display success only after backend reports `published`.
- Safe retry must use the backend retry endpoint.
- Manual handoff is a separate outcome and must not visually resemble confirmed publication.
- External post URL appears only when returned by backend.

---

## 16. Error and Recovery Matrix

| Situation | Frontend behavior |
|---|---|
| Project create fails | Keep form values, show retryable error |
| Planning fails | Show error and retry plan action if supported |
| Upload fails | Mark only failed asset, allow retry/remove |
| Generation provider fails | Show failed stage + safe backend message |
| Job polling/SSE disconnects | Show reconnecting state; do not mark job failed |
| Generation job fails | Show retry when backend permits |
| Scene fails | Allow scene retry/regeneration where supported |
| Quality warning | Display warning without inventing failure |
| Approval fails | Keep user on review page and refetch version state |
| Publish fails | Show publish failure and safe retry |
| Qoneqt unavailable | Offer Manual Handoff if backend supports it |
| External analytics unavailable | Show unavailable/unsupported state, not zero |
| Provider not configured | Disable dependent action with explanation |
| 401 | Route to auth flow once authentication UX exists |
| 403 | Show permission error |
| 404 | Show not-found state |
| 429 | Show rate-limit feedback and avoid rapid retry loop |

---

## 17. Loading and Empty States

Every data surface must define these states.

### Project library
- Loading skeleton.
- No projects.
- No search/filter results.
- API error.

### Dashboard
- Loading.
- New user / no data.
- Partial data if one widget fails.
- Full error.

### Storyboard
- Planning in progress.
- No storyboard yet.
- Storyboard loaded.
- Save error.

### Review
- Preview loading.
- Preview unavailable.
- Quality report loading.
- Quality report unavailable/error.

### Analytics
- No external analytics access.
- Published but metrics not yet available.
- Metrics available.
- Retrieval error.

---

## 18. Accessibility

Minimum requirements:
- Keyboard-accessible controls.
- Visible focus states.
- Form labels tied to inputs.
- Do not communicate status by color alone.
- `aria-live` region for meaningful job-status changes.
- Captions/settings controls have text labels.
- Dialogs trap focus and restore focus when closed.
- Video controls accessible through native controls or an accessible player.
- Adequate contrast.
- Respect reduced-motion preference for decorative animations.

---

## 19. Responsive Behavior

### ≥ 1200px
- Full sidebar.
- Two-column storyboard/review layouts.
- Persistent contextual settings panel.

### 768–1199px
- Compact sidebar.
- Two-column layouts collapse selectively.
- Scene cards remain readable.

### < 768px
- Navigation drawer.
- Single-column forms.
- Sticky bottom primary action where helpful.
- Quality and publish panels stack.
- Tables become cards or horizontally scroll only when necessary.

The challenge demo should be optimized first for a standard laptop viewport.

---

## 20. Visual Design Direction

The PRD does not prescribe a brand system, so frontend design should remain product-focused.

Recommended direction:
- Modern creator-tool dashboard.
- Neutral application shell.
- Strong visual emphasis on video preview and current workflow stage.
- One primary accent color.
- Status colors used consistently.
- Rounded cards with restrained shadows/borders.
- Clear typography hierarchy.
- Minimal decorative animation.
- Video aspect-ratio previews should visually resemble the final output format.

Avoid:
- Over-designed AI gradients on every surface.
- Fake waveform/progress animations implying backend work.
- Dense professional-editor timeline UI; a full timeline editor is explicitly outside MVP scope.
- Controls for unsupported provider features.

---

## 21. State Management

Keep server state and local UI state separate.

Recommended categories:

### Server state
- Projects.
- Project detail.
- Storyboard.
- Jobs.
- Quality report.
- Preview.
- Publishing status.
- Analytics.
- Provider capabilities.

Use a server-state library such as TanStack Query if permitted by the existing project.

### Local state
- Form drafts.
- Modal open/closed.
- Selected tab.
- Unsaved scene edits.
- Temporary upload selection.

Do not duplicate entire server project objects into a global client store without need.

---

## 22. Recommended Frontend Dependencies

Only add libraries that materially reduce implementation risk.

Suggested:
- React.
- React Router.
- TanStack Query.
- React Hook Form.
- Zod if shared/client validation is useful.
- A lightweight accessible component system or existing project UI library.
- Native `EventSource` for SSE when auth architecture allows it.

Dependency choices should follow the existing repository where possible.

---

## 23. Frontend Security Requirements

- No provider credentials in frontend code.
- No secrets in `VITE_*` environment variables.
- Treat signed preview/upload URLs as sensitive temporary URLs.
- Do not render raw HTML from model/provider output without sanitization.
- Escape user-generated project titles/scripts in normal rendering.
- Validate file selection before upload, while relying on server validation as authoritative.
- Do not expose internal stack traces.
- Do not store sensitive auth tokens in insecure storage if backend auth architecture provides a safer cookie/session mechanism.
- Enforce route UX permissions, but never rely on frontend checks as actual authorization.

---

## 24. P0 / P1 / P2 Frontend Scope

### P0 — Required for core demo
- App shell/navigation.
- Dashboard with real internal counts.
- Create project.
- Topic/script input.
- Reference image upload.
- Language/duration/aspect/theme/effort/caption settings.
- AI planning trigger.
- Script display/edit.
- Storyboard display/edit.
- Generate video action.
- Real generation progress.
- Cancel/retry job where backend supports it.
- Final video preview.
- Quality report.
- Exact-version approval.
- Automatic Qoneqt publishing if supported.
- Manual handoff when automatic publishing is unavailable.
- Project library/history.
- Honest loading/error/unavailable states.

### P1 — High-value
- Hook alternatives.
- Individual scene regeneration UI.
- Voice preview.
- Music selection.
- Caption styling.
- Thumbnail.
- Project duplication.
- Search/filter improvements.
- Trend dashboard.
- External analytics.
- AI performance insights.
- Provider status screen.
- Brand kit.
- Rich quality findings/repair suggestions.
- SRT/VTT export.

### P2 — Later
- Scheduling.
- Multi-account publishing.
- Team approval workflows.
- Advanced word-level caption highlighting.
- Pronunciation dictionary.
- A/B comparison UI.
- Content calendar.
- Advanced historical personalization.

---

## 25. Frontend Implementation Order

The frontend should be built only after the relevant backend contracts work.

### Phase F0 — Foundation
1. Inspect existing React/Vite repository.
2. Configure routing.
3. Configure API client.
4. Add app shell.
5. Add error/toast/loading primitives.
6. Define API/domain types.

**Exit:** frontend can call `/api/v1/health` or a basic authenticated endpoint and render real response state.

### Phase F1 — Projects and Create Flow
1. Project library.
2. Create project form.
3. Asset upload.
4. Project detail shell.
5. Settings summary.

**Exit:** user can create and reopen a persisted project.

### Phase F2 — AI Plan and Storyboard
1. Trigger plan.
2. Render content brief.
3. Script editor.
4. Storyboard editor.
5. Save edits.
6. Hook variants/scene regeneration only after core editing works.

**Exit:** user can generate, review, edit, save, and reload a real storyboard.

### Phase F3 — Generation
1. Queue generation.
2. Generate idempotency key.
3. Build job progress page.
4. Add SSE/polling.
5. Add cancellation/retry.
6. Recover active job after refresh.

**Exit:** real backend generation can be observed without fake progress.

### Phase F4 — Review and Approval
1. Preview player.
2. Quality report.
3. Findings UI.
4. Export.
5. Exact-version approval.

**Exit:** final artifact can be reviewed and approved.

### Phase F5 — Publishing
1. Fetch publishing capability.
2. Automatic publish flow when available.
3. Publish job progress.
4. Retry.
5. Manual handoff fallback.

**Exit:** frontend accurately represents confirmed publication or manual handoff.

### Phase F6 — Dashboard and Analytics
1. Internal metrics.
2. Recent projects/jobs.
3. External analytics only when real source exists.
4. Insights/trends as P1.

### Phase F7 — Demo Hardening
1. Responsive pass.
2. Accessibility pass.
3. Failure-state testing.
4. Refresh/recovery testing.
5. Provider-unavailable testing.
6. Empty-state testing.
7. Remove all mock/hard-coded demo data from production demo paths.

---

## 26. Frontend Acceptance Tests

### Create flow
- [ ] User can create a project from a topic.
- [ ] User can create a project from a script.
- [ ] Invalid required input is blocked.
- [ ] Supported settings are submitted correctly.
- [ ] Reference image upload failures are visible and recoverable.

### Planning/storyboard
- [ ] User can trigger a real plan request.
- [ ] Script and storyboard returned by backend are displayed.
- [ ] User can edit and persist supported fields.
- [ ] Reload shows saved server data.

### Generation
- [ ] Generation submit creates only one job for one action.
- [ ] UI handles HTTP 202 correctly.
- [ ] Real backend progress/stage is displayed.
- [ ] Refresh does not restart the job.
- [ ] Failed job shows safe error.
- [ ] Retry/cancel work when permitted.
- [ ] UI never increments fake progress.

### Review
- [ ] Authorized preview plays.
- [ ] Quality report is displayed.
- [ ] Warnings and failures are visually distinct.
- [ ] User can approve the exact displayed version.
- [ ] Editing/regeneration invalidates stale approval in the UI after backend state refresh.

### Publishing
- [ ] Publish is unavailable before approval.
- [ ] Automatic publishing is shown only when capability exists.
- [ ] Accepted publish request is not immediately labelled published.
- [ ] Published state appears only after backend confirmation.
- [ ] Publish failure can be retried safely when allowed.
- [ ] Manual handoff is clearly labelled and never displayed as automatic publication.

### Analytics
- [ ] Internal counts match backend records.
- [ ] External metrics are not shown as real unless returned by authorized analytics.
- [ ] Unsupported analytics show an unavailable state rather than fake zeros.

### Security
- [ ] No provider key exists in client bundle/config.
- [ ] Raw provider errors/secrets are not displayed.
- [ ] Unauthorized project access is not treated as normal missing data.

---

## 27. Definition of Frontend MVP Done

The frontend MVP is complete when a user can:

1. Create a real persisted project.
2. Submit a topic or script and optional reference image.
3. Configure supported generation settings.
4. Generate a real AI brief/script/storyboard.
5. Review and edit the plan.
6. Queue a real asynchronous generation job.
7. Observe real backend progress and recover after refresh.
8. Preview the resulting MP4.
9. Read the real quality report.
10. Approve the exact final version.
11. Publish through the authorized Qoneqt path when available, or use an explicitly labelled manual handoff.
12. Reopen the project from history.
13. See internal dashboard metrics based on stored records.
14. Encounter no critical screen whose success state depends on hard-coded fake data.

---

## 28. Backend Dependencies / Open Questions

Frontend implementation should not guess these values. Confirm them from the backend before final wiring:

1. Authentication/session mechanism.
2. Exact request/response schemas for every `/api/v1` endpoint.
3. Whether job progress uses SSE, polling only, or both.
4. Upload flow and file constraints.
5. Provider capability response shape.
6. Preview/export URL lifetime and authorization.
7. Exact version identifier used for approval.
8. Quality-report schema and severity levels.
9. Whether project `status` and generation job `status` are separate fields in all responses.
10. Qoneqt account capability schema.
11. Supported publish metadata fields.
12. External analytics availability and schema.
13. Cost estimate/actual-cost response shape.
14. Pagination format.
15. Whether project deletion is immediate or asynchronous.
16. Which options must be dynamically disabled based on provider limitations.

Until these contracts exist, build typed adapters/interfaces rather than embedding assumptions throughout components.

---

## 29. Final Frontend Principle

**The frontend is a transparent control surface over the real generation pipeline.**

Its job is not to make the system appear faster, smarter, or more connected than it is. Its job is to make the real workflow easy to understand and control: create, plan, generate, recover, review, approve, publish, and learn from actual results.

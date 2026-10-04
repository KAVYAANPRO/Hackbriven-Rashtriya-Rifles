# PRD — From Idea to Feed
### An AI-powered content production pipeline for the Qoneqt Global Feed

Team: Rashtriya Rifles · College: Airport School of Technology

---

## 1. Problem

Qoneqt needs a steady supply of finished, publish-ready short vertical videos for the
Global Feed — not one-off experiments. Today:

- AI can generate individual pieces (a script, an image, a clip) but **nobody owns the
  pipeline** end-to-end.
- Every new topic restarts the whole chain: idea → script → hook → storyboard →
  visuals → voiceover → captions → edit → quality check → export — ten disconnected
  steps, hand-stitched by a person.
- Existing options are either manual editing across separate tools, or one-prompt
  AI video tools with no control over script, timing, or captions.

**Key gaps:** no structure (no scenes/timing plan), no validation (broken audio or
captions get exported anyway), tied to one model (a quota or API change halts
production), hard to repeat (quality depends on the person operating the tools).

## 2. Solution

One input — a topic, prompt, idea, or trend — drives one automated pipeline that
produces one publish-ready vertical MP4. The script becomes structured JSON scenes,
so every downstream step is automated, testable, and repeatable, with fallback chains
at every external API call so a single provider's rate limit or outage never stops
production.

```
IDEA → SCRIPT/HOOK → STORYBOARD → VISUALS → VOICEOVER → CAPTIONS → EDIT → QUALITY CHECK → EXPORT
```
collapses to:
```
INPUT → INTELLIGENCE → GENERATION → COMPOSITION → VALIDATION → OUTPUT
```

## 3. Who is affected / who benefits

- **Content teams and creators** feeding the Qoneqt Global Feed — idea to finished
  video in one run instead of a manual multi-tool workflow.
- **Qoneqt** — a consistent, repeatable supply of Global Feed videos, independent of
  any one operator's skill.
- **Impact** — replaces manual scripting, voiceover, editing, and captioning.

## 4. Non-goals (for this build)

- No model training — built entirely on free/open APIs and libraries.
- No database — job state lives in memory; artifacts live on disk as files.
- No multi-tenant auth/billing system in the first pass — single-operator or
  small-team usage.

## 5. Core pipeline stages (functional requirements)

| Stage | Input | Output | Responsibility |
|---|---|---|---|
| **1. Input** | Topic / prompt / idea / trend (string) | Validated job request | Accept one input, create a job |
| **2. Intelligence — Story Engine** | Topic | Structured JSON script: hook, scenes, image prompts, durations, mood | Gemini Flash primary, Groq fallback |
| **3. Intelligence — Scene Planner** | Script JSON | Per-scene plan: narration, image prompt, duration, timing offsets | Derived deterministically from script JSON |
| **4. Generation — Images** | Per-scene image prompt | One image per scene | NVIDIA Stable Diffusion 3.5 primary, Pollinations fallback |
| **5. Generation — Voice** | Per-scene narration | One narrated audio clip per scene | edge-tts neural voice |
| **6. Generation — Captions** | Voice audio | Word-level timestamps | Whisper |
| **7. Composition** | Images + voice + captions | Silent-scene video with motion | Ken Burns pan/zoom, karaoke-style synced captions burned in, music ducked under narration, loudness-normalised, H.264 export (ffmpeg + Pillow) |
| **8. Validation — Quality Gate** | Composed MP4 | Pass/fail + reasons | ffprobe checks: resolution (1080×1920), duration matches plan, audio track present and non-silent; triggers regenerate-or-repair on failure |
| **9. Output** | Validated MP4 | Publish-ready vertical video | Delivered as a file the job can be marked "ready for Feed" |

## 6. Non-functional requirements

- **Resilience:** every external API call (script LLM, image model, motion model) has
  a configured fallback chain; a rate limit or outage degrades gracefully, it never
  hard-fails the job.
- **Repeatability:** identical topic + identical model config ⇒ same pipeline shape
  (scene count, stage order); stochastic outputs (image/voice content) may vary.
- **Statelessness per job:** each topic is one independent job; jobs do not share
  mutable state. Scaling is "one more job in the queue."
- **Observability:** every stage reports status (queued → running → done → failed)
  so a caller can poll live progress per job.
- **Testability offline:** every service call is mockable; the pipeline logic must be
  fully testable without live API keys (30+ unit tests per the original prototype).
- **Cost:** near-zero — free tiers (Gemini, Groq, NVIDIA credits, edge-tts,
  Pollinations); optional paid motion (fal.ai LTX, ~$0.02/clip) is opt-in, not
  required.
- **Performance target:** ~45s to produce a ~23s video on 1 CPU (reference figure
  from the prototype; not a hard SLA for this build).

## 7. Build phases

### Phase 0 — Foundations
Project scaffold, configuration/secrets loading, shared Pydantic schemas
(Script, Scene, Job, QualityReport), structured logging, in-memory job manager,
custom exception hierarchy. No external calls yet.

### Phase 1 — Intelligence (Story Engine + Scene Planner)
Gemini Flash integration returning structured JSON (hook, scenes, image prompts,
durations, mood) with a Groq fallback on failure/timeout/rate-limit. Scene Planner
derives a deterministic per-scene execution plan from the script JSON. Prompt
templates enforce a strict JSON schema; responses are validated and repaired
(re-prompt on invalid JSON) before moving on.

### Phase 2 — Generation (Images, Voice, Captions)
Model Router with configurable provider chains:
- Images: NVIDIA Stable Diffusion 3.5 → Pollinations fallback.
- Voice: edge-tts neural narration, one clip per scene.
- Captions: Whisper word-level timestamps from the generated voice audio.

Every provider call is wrapped so failures fall through the chain instead of
aborting the job.

### Phase 3 — Composition
Video Composer combines per-scene images + audio + captions into a single vertical
video: Ken Burns pan/zoom motion (Pillow), karaoke-style word-synced caption
burn-in, background-music ducking under narration, loudness normalisation, H.264
MP4 export (ffmpeg). Optional fal.ai LTX motion clip can replace Ken Burns per
scene when configured.

### Phase 4 — Validation (Quality Gate)
ffprobe-based checks: resolution is 1080×1920, duration matches the planned total
within tolerance, an audio track exists and is not silent. On failure, the gate
returns actionable reasons and the pipeline can regenerate or repair the specific
failing stage rather than restarting the whole job.

### Phase 5 — Orchestration & API
Pipeline orchestrator chains stages 1–9, updates job status after each stage, and
persists stage outputs/artifacts under a per-job directory. A thin HTTP API (FastAPI)
exposes: create job, get job status/progress, get job result (video path/URL),
list jobs. This API is the contract the Gradio frontend (and any future frontend)
consumes.

### Phase 6 — Frontend (Gradio) — scaffolded
Topic input box, live per-stage status, video preview on completion. Talks only to
the Phase 5 API (`frontend/app.py`, polls `GET /jobs/{id}`).

### Phase 7 — Deployment & Hardening — scaffolded
`Dockerfile` (installs `ffmpeg`, runs `app.py`), root `app.py` bundling backend +
Gradio into one process for a Hugging Face Space, `deploy/huggingface/README.md`
(Space card template), and `.github/workflows/ci.yml` running the offline test
suite. Config-driven model names are already in place (`backend/config.py`).
Wake-before-demo handling for free Spaces sleeping on idle is a manual step at
demo time, not code.

## 8. Success criteria for the backend (Phases 0–5)

1. A single call with a topic string produces a job id.
2. Polling the job shows monotonic stage progression with no stage skipped.
3. Killing/blocking a primary provider (simulated in tests) causes fallback to the
   secondary provider, and the job still completes.
4. The quality gate rejects a deliberately malformed video (wrong resolution/no
   audio) in a unit test, and accepts a valid one.
5. The full stage chain runs against mocked providers in CI with no network access
   and no API keys, and passes.
6. Real `ffmpeg`/`ffprobe` composition produces a playable MP4 when given real
   local input images + audio (integration test, run locally where ffmpeg is
   installed).

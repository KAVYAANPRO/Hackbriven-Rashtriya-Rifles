# TECH.md — Architecture & Stack

## 1. Stack summary

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Every required library (ffmpeg bindings, Whisper, edge-tts, Gradio) is Python-first |
| Backend API | FastAPI + Uvicorn | Async-friendly, typed, auto docs, thin layer over the pipeline |
| Frontend (later phase) | Gradio | Matches the original prototype: topic input, live stage status, video preview |
| Script/story LLM | Gemini (primary) → Groq → OpenRouter → local template (last resort) | Structured JSON generation; three independent LLM providers, plus a keyless deterministic template so the stage never hard-fails for lack of an API key |
| Image generation | NVIDIA-hosted FLUX.1-dev (primary) → Pollinations (free, no key) → local gradient+text placeholder (last resort) | Enumerated request sizes from both external providers are center-cropped to the target aspect ratio; the stage can never hard-fail |
| Voice | `edge-tts` | Free, no API key, good neural voices |
| Captions | `faster-whisper` (CPU, int8) | Word-level timestamps for karaoke captions; resumable `huggingface_hub` model download (see §7 for why not `openai-whisper`) |
| Motion (optional) | fal.ai LTX (paid, ~$0.02/clip) → Ken Burns (ffmpeg/Pillow, free, always available) | Ken Burns is the default; fal.ai is opt-in via config |
| Composition | `ffmpeg` (via `ffmpeg-python` / subprocess) + `Pillow` | Industry standard, scriptable, no GPU required |
| Validation | `ffprobe` | Ground-truth media inspection: resolution, duration, audio stream presence |
| Job state | In-process dict behind a thin manager (`JobManager`) | PRD explicitly calls for "no database needed" |
| Storage | Local filesystem, one directory per job under `storage/jobs/<job_id>/` | Matches "files on the Space disk" from the prototype |
| Config | `pydantic-settings` + `.env` | Typed, validated env config; model names are config, not hardcoded |
| Testing | `pytest` + `pytest-mock` / `unittest.mock` | All provider calls mocked so the suite runs with zero network/API keys |

## 2. Repository layout

```
HACKBRIVEN-1/
├── PRD.md
├── TECH.md
├── RULES.md
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── backend/
│   ├── config.py                 # Settings (pydantic-settings), model name registry
│   ├── models/
│   │   └── schemas.py            # Scene, Script, Job, QualityReport, enums
│   ├── core/
│   │   ├── exceptions.py         # Typed exception hierarchy
│   │   ├── job_manager.py        # In-memory job store + status transitions
│   │   └── pipeline.py           # Orchestrator: chains all stages for one job
│   ├── services/
│   │   ├── model_router.py       # Generic "try providers in order" helper
│   │   ├── story_engine.py       # Stage 2: Gemini -> Groq
│   │   ├── scene_planner.py      # Stage 3: script JSON -> per-scene plan
│   │   ├── image_generator.py    # Stage 4: NVIDIA FLUX.1-dev -> Pollinations -> local placeholder
│   │   ├── voice_generator.py    # Stage 5: edge-tts
│   │   ├── caption_generator.py  # Stage 6: Whisper word timestamps
│   │   ├── video_composer.py     # Stage 7: ffmpeg/Pillow composition
│   │   └── quality_gate.py       # Stage 8: ffprobe validation
│   ├── utils/
│   │   ├── ffmpeg_utils.py       # subprocess wrappers around ffmpeg/ffprobe
│   │   └── logger.py             # Structured logging setup
│   └── api/
│       ├── main.py               # FastAPI app factory
│       └── routes.py             # /jobs endpoints
├── frontend/                     # Phase 6 (Gradio) — not built in this pass
├── storage/
│   └── jobs/                     # Per-job artifacts (.gitkeep only, contents ignored)
└── tests/
    ├── conftest.py
    ├── test_schemas.py
    ├── test_job_manager.py
    ├── test_story_engine.py
    ├── test_scene_planner.py
    ├── test_image_generator.py
    ├── test_video_composer.py
    ├── test_quality_gate.py
    └── test_pipeline.py
```

## 3. Data flow (request lifecycle)

```
POST /jobs {topic}
        │
        ▼
JobManager.create() ──► job_id, status=QUEUED
        │
        ▼
Pipeline.run(job_id)                         (background task)
   │
   ├─ 1. INTELLIGENCE   story_engine.generate_script(topic)
   │                     └─ Gemini ──fail──► Groq ──fail──► OpenRouter ──fail──► local template
   │                    scene_planner.plan(script) -> list[ScenePlan]
   │
   ├─ 2. GENERATION      for each scene, in parallel-safe sequence:
   │                     image_generator.generate(prompt) : NVIDIA ──fail──► Pollinations ──fail──► local placeholder
   │                     voice_generator.synthesize(narration) : edge-tts
   │                     caption_generator.transcribe(audio) : Whisper word timestamps
   │
   ├─ 3. COMPOSITION     video_composer.compose(scenes, assets) -> raw.mp4
   │                     Ken Burns + caption burn-in + ducking + loudness norm + H.264 export
   │
   ├─ 4. VALIDATION      quality_gate.check(raw.mp4, plan) -> QualityReport
   │                     fail -> repair/regenerate the specific failing stage, re-validate
   │                     (bounded retries, then job FAILED with reasons)
   │
   └─ 5. OUTPUT          job.status = DONE, job.result_path = final.mp4

GET /jobs/{id}      -> status, current stage, per-stage timestamps
GET /jobs/{id}/result -> file path / download of final.mp4
```

Every stage function is pure with respect to its declared inputs/outputs (topic in,
script JSON out; script in, scene plan out; etc.) so each is independently unit
testable and independently re-runnable — matching the PRD's "any stage can be
re-run or swapped" requirement.

## 4. Fallback chain pattern

All provider calls go through `services/model_router.py`:

```python
def call_with_fallback(providers: list[Callable[[], T]], *, stage: str) -> T:
    """Try each provider in order; return the first success; raise PipelineError
    with all collected errors if every provider fails."""
```

Each service builds its provider list from `config.py` (so swapping/retiring a
model is a config change), then calls `call_with_fallback`. This is the single
implementation of the "Gemini→Groq→OpenRouter→local template, NVIDIA→Pollinations→
local placeholder, fal.ai→Ken Burns" pattern
described in the PRD — one mechanism, reused per stage rather than reimplemented.

## 5. Job state machine

```
QUEUED -> RUNNING_INTELLIGENCE -> RUNNING_GENERATION -> RUNNING_COMPOSITION
       -> RUNNING_VALIDATION -> DONE
                              \-> FAILED (with stage + reason)
```

`JobManager` is a simple thread-safe dict (`threading.Lock`-guarded) mapping
`job_id -> Job`. No database, per the PRD; this is intentional and documented, not
an oversight — swapping in persistent storage later only touches `JobManager`.

## 6. Configuration & secrets

`backend/config.py` uses `pydantic-settings.BaseSettings` to load from `.env`:

- `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`
- `NVIDIA_API_KEY` (Pollinations and the local placeholder need no key)
- `FAL_API_KEY` (optional; motion stage is skipped/Ken-Burns-only if unset)
- `GEMINI_MODEL`, `GROQ_MODEL`, `OPENROUTER_MODEL`, `NVIDIA_IMAGE_MODEL`,
  `WHISPER_MODEL` — model **names**
  are config values, never hardcoded in service code, so a model retirement is a
  one-line `.env` change.
- `STORAGE_DIR` — root for per-job artifacts (defaults to `storage/jobs`).
- `TARGET_RESOLUTION` (`1080x1920`), `MAX_REGENERATE_ATTEMPTS`.

No secret is ever logged or committed; `.env` is git-ignored, `.env.example`
documents every key with a placeholder.

## 7. External dependencies

`ffmpeg`/`ffprobe`: preferred from `PATH` if present, otherwise
`backend/utils/ffmpeg_utils.py` transparently falls back to the `static-ffmpeg`
pip package, which fetches a static build into a user-writable cache on first
use — no system install or admin rights required. All of this is declared in
`README.md` setup instructions.

**Why `faster-whisper`, not `openai-whisper`:** live-tested both. The original
`openai-whisper` package downloads its model weights with a plain `urllib`
call that has no timeout and isn't resumable — on this project's dev machine
the download stalled part-way through and hung indefinitely (confirmed: the
process sat at 0% CPU progress for 15+ minutes with a dead-but-open TCP
connection). `faster-whisper` downloads the same weights via
`huggingface_hub`, which chunks and resumes properly. Separately, the `av`
package `faster-whisper` uses for file-path audio decoding had an ABI
mismatch on this Python/OS combination with no compatible prebuilt wheel
available; `caption_generator._decode_audio` sidesteps this entirely by
shelling out to the already-resolved `ffmpeg` binary to produce a raw
16kHz mono float32 PCM buffer and handing that array to
`WhisperModel.transcribe()` directly, which skips `av` altogether.

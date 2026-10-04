# RULES.md — Engineering rules for this repo

These rules exist so the pipeline stays what the PRD promises: structured,
validated, provider-agnostic, and repeatable. Follow them for any change in
`backend/`.

## 1. Stage contracts are sacred

- Every pipeline stage is a function with a typed input and a typed output
  (Pydantic models in `backend/models/schemas.py`). Never pass raw dicts between
  stages — validate at the boundary.
- A stage must not reach into another stage's internals. If Stage 7 needs
  something from Stage 2, it comes through the `Script`/`ScenePlan` object, not
  by re-deriving it or importing Stage 2's internals.
- Any stage must be independently callable and independently unit-testable
  without running the stages before it (use fixtures/mocked inputs).

## 2. No provider call without a fallback chain

- Every external API call (LLM, image model, motion model) is registered as an
  ordered provider list in `config.py` and invoked only through
  `services/model_router.call_with_fallback`.
- Never call a provider SDK directly from a stage service — always go through the
  router, even if today there is only one provider. That's how a second provider
  gets added later without touching the stage logic.
- A provider failure (timeout, rate limit, malformed response) must be caught and
  logged with the provider name and stage, then the next provider in the chain is
  tried. Only raise `PipelineError` when the whole chain is exhausted.

## 3. Model names are config, never hardcoded

- No string literal like `"gemini-1.5-flash"` inside a service module. It lives in
  `config.py` / `.env`, referenced by name. A model retirement must be fixable by
  editing `.env`, not by editing code.

## 4. Validate before you trust

- LLM JSON output is untrusted until parsed into the `Script`/`Scene` Pydantic
  model. Invalid JSON triggers one re-prompt with the validation error appended
  before falling back to the next provider.
- The quality gate (`ffprobe`) is the only source of truth for "is this video
  good" — never assume composition succeeded just because ffmpeg exited 0. Check
  the actual output file.

## 5. No database, no hidden mutable global state

- Job state lives only in `JobManager`, guarded by a lock. Do not add module-level
  mutable globals elsewhere to track progress, cache results, etc.
- Per-job artifacts live under `storage/jobs/<job_id>/`; never write pipeline
  output outside that directory.

## 6. Tests run offline, always

- Every new service must ship with unit tests that mock the network/subprocess
  boundary (`unittest.mock.patch` on the HTTP client / `subprocess.run`). CI has
  no API keys and no network access — if a test needs either, it's broken.
- `ffmpeg`/`ffprobe` integration tests that need the real binaries are marked
  (`@pytest.mark.integration`) and skipped by default; the default `pytest` run
  must be 100% offline and fast.
- Do not delete or weaken an existing test to make a change land. Fix the code or
  fix the test's assumptions explicitly, and say which.

## 7. Errors carry stage + reason, always

- Every exception raised out of a stage is a subclass of `PipelineError` (see
  `core/exceptions.py`) and carries `stage: str` and a human-readable `reason`.
  A bare `Exception`/`ValueError` must never cross a stage boundary uncaught.
- `Pipeline.run` catches `PipelineError`, marks the job `FAILED` with the stage and
  reason attached, and stops. It does not silently continue to the next stage.

## 8. Style

- Type hints on every function signature; this is a typed codebase.
- No bare `except:`; catch specific exceptions.
- No comments explaining *what* the code does — name things so it's obvious.
  Comments are reserved for *why* (a workaround, a non-obvious constraint).
- Don't build abstractions for a second provider/stage that doesn't exist yet.
  The router pattern (rule 2) is the one deliberate exception, because the PRD
  requires it for every stage from day one.
- Keep functions small enough that a unit test can target one behavior.

## 9. Scope discipline

- Backend phases (0–5) do not implement the Gradio frontend or deployment
  scripts — those are Phase 6/7, tracked separately in `PRD.md`. Don't blur the
  phases; a change belongs to the phase whose success criteria it serves.
- Don't add auth, a database, or multi-tenancy speculatively. The PRD is explicit
  that none of these are required for this build.

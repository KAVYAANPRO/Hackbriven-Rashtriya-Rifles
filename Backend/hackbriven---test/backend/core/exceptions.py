from __future__ import annotations


class PipelineError(Exception):
    """Base error for any failure that crosses a pipeline stage boundary."""

    def __init__(self, stage: str, reason: str) -> None:
        self.stage = stage
        self.reason = reason
        super().__init__(f"[{stage}] {reason}")


class AllProvidersFailedError(PipelineError):
    """Every provider in a fallback chain failed for a stage."""

    def __init__(self, stage: str, errors: list[tuple[str, str]]) -> None:
        self.errors = errors
        detail = "; ".join(f"{name}: {msg}" for name, msg in errors)
        super().__init__(stage, f"all providers failed -> {detail}")


class InvalidScriptError(PipelineError):
    """LLM output could not be parsed/validated into a Script."""


class CompositionError(PipelineError):
    """ffmpeg/Pillow composition failed."""


class QualityGateError(PipelineError):
    """Composed video failed validation and could not be repaired."""


class JobNotFoundError(Exception):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"job not found: {job_id}")


class InvalidJobStateError(Exception):
    """Raised when a lifecycle action (approve/cancel/publish) is attempted
    on a job that isn't in a state that permits it."""

    def __init__(self, job_id: str, current_status: str, action: str) -> None:
        self.job_id = job_id
        self.current_status = current_status
        self.action = action
        super().__init__(f"cannot {action} job {job_id}: current status is {current_status}")

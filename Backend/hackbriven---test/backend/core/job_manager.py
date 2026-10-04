from __future__ import annotations

import threading

from datetime import datetime, timezone

from backend.config import settings
from backend.core.exceptions import JobNotFoundError
from backend.models.schemas import Job, JobStatus, Language, MotionTier, ProviderEvent, StageTimestamp

_mongo_client = None


def _use_mongo() -> bool:
    return bool(settings.mongodb_uri)


def _mongo_collection():
    global _mongo_client
    if _mongo_client is None:
        import pymongo

        _mongo_client = pymongo.MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=10000)
    return _mongo_client[settings.mongodb_db_name]["jobs"]


def _to_doc(job: Job) -> dict:
    doc = job.model_dump(mode="json")
    doc["_id"] = job.id
    return doc


def _from_doc(doc: dict) -> Job:
    doc = dict(doc)
    doc.pop("_id", None)
    return Job(**doc)


class JobManager:
    """Job store. In-memory dict is always the fast-path cache; when
    MONGODB_URI is configured, every write also persists to Mongo and every
    cache miss on get()/list() falls back to it, so job state (and the
    user's generation history) survives a process restart - a real
    requirement once this pipeline deploys anywhere with ephemeral storage,
    not just a "nice to have". Falls back to pure in-memory (original
    design) when no URI is configured, so local dev needs no Mongo at all.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def _persist(self, job: Job) -> None:
        if _use_mongo():
            _mongo_collection().replace_one({"_id": job.id}, _to_doc(job), upsert=True)

    def create(
        self,
        topic: str,
        *,
        motion_tier: MotionTier = MotionTier.BALANCED,
        language: Language = Language.EN,
        idempotency_key: str | None = None,
        owner: str | None = None,
        reference_images: list[str] | None = None,
        style: str = "auto",
        style_prompt: str | None = None,
        resolution: str = "1080p",
    ) -> Job:
        if idempotency_key:
            existing = self.find_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing

        job = Job(
            topic=topic,
            motion_tier=motion_tier,
            language=language,
            idempotency_key=idempotency_key,
            owner=owner,
            reference_images=list(reference_images or []),
            style=style,
            style_prompt=style_prompt,
            resolution=resolution,
        )
        job.history.append(StageTimestamp(stage="input", status="accepted"))
        with self._lock:
            self._jobs[job.id] = job
            self._persist(job)
        return job

    def find_by_idempotency_key(self, idempotency_key: str) -> Job | None:
        """Repeated job-creation requests with the same Idempotency-Key must
        return the original job rather than starting a duplicate run and
        charging credits twice (PRD 6.6: "avoid duplicate jobs ... using
        idempotency keys")."""
        with self._lock:
            for job in self._jobs.values():
                if job.idempotency_key == idempotency_key:
                    return job
        if _use_mongo():
            doc = _mongo_collection().find_one({"idempotency_key": idempotency_key})
            if doc is not None:
                job = _from_doc(doc)
                with self._lock:
                    self._jobs.setdefault(job.id, job)
                return job
        return None

    def approve(self, job_id: str, *, approver: str) -> Job:
        from backend.core.exceptions import InvalidJobStateError

        with self._lock:
            job = self._get_locked(job_id)
            if job.status != JobStatus.DONE:
                raise InvalidJobStateError(job_id, job.status.value, "approve")
            job.status = JobStatus.APPROVED
            job.approved_by = approver
            job.approved_at = datetime.now(timezone.utc)
            job.history.append(StageTimestamp(stage=JobStatus.APPROVED.value, status=f"approved by {approver}"))
            job.touch()
            self._persist(job)
            return job

    def cancel(self, job_id: str) -> Job:
        from backend.core.exceptions import InvalidJobStateError

        _TERMINAL = {
            JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.APPROVED,
            JobStatus.PUBLISHING, JobStatus.PUBLISHED, JobStatus.PUBLISH_FAILED, JobStatus.MANUAL_HANDOFF,
        }
        with self._lock:
            job = self._get_locked(job_id)
            if job.status in _TERMINAL:
                raise InvalidJobStateError(job_id, job.status.value, "cancel")
            job.status = JobStatus.CANCELLED
            job.history.append(StageTimestamp(stage=JobStatus.CANCELLED.value, status="cancelled by request"))
            job.touch()
            self._persist(job)
            return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                return job
            if _use_mongo():
                doc = _mongo_collection().find_one({"_id": job_id})
                if doc is not None:
                    job = _from_doc(doc)
                    self._jobs[job_id] = job
                    return job
        raise JobNotFoundError(job_id)

    def list(self) -> list[Job]:
        if _use_mongo():
            # Mongo is the durable source of truth across restarts - a
            # fresh process has nothing in self._jobs yet, so list() must
            # read from there, not just whatever this process has seen.
            docs = _mongo_collection().find().sort("created_at", -1)
            jobs = [_from_doc(doc) for doc in docs]
            with self._lock:
                for job in jobs:
                    self._jobs.setdefault(job.id, job)
            return jobs
        with self._lock:
            return list(self._jobs.values())

    def add_provider_event(self, job_id: str, event: ProviderEvent) -> None:
        with self._lock:
            job = self._get_locked(job_id)
            job.provider_events.append(event)
            job.touch()
            self._persist(job)

    def set_status(self, job_id: str, status: JobStatus, *, note: str = "") -> Job:
        with self._lock:
            job = self._get_locked(job_id)
            if job.status == JobStatus.CANCELLED and status != JobStatus.CANCELLED:
                # A stage that was already in flight when the user cancelled
                # must not resurrect the job.
                return job
            job.status = status
            job.history.append(
                StageTimestamp(stage=status.value, status=note or "entered")
            )
            job.touch()
            self._persist(job)
            return job

    def mark_failed(self, job_id: str, *, stage: str, reason: str) -> Job:
        with self._lock:
            job = self._get_locked(job_id)
            job.status = JobStatus.FAILED
            job.error_stage = stage
            job.error_reason = reason
            job.history.append(StageTimestamp(stage=stage, status=f"failed: {reason}"))
            job.touch()
            self._persist(job)
            return job

    def update(self, job_id: str, **fields: object) -> Job:
        with self._lock:
            job = self._get_locked(job_id)
            for key, value in fields.items():
                setattr(job, key, value)
            job.touch()
            self._persist(job)
            return job

    def _get_locked(self, job_id: str) -> Job:
        """Like get(), but assumes self._lock is already held - avoids
        re-entrant locking in the mutator methods above."""
        job = self._jobs.get(job_id)
        if job is not None:
            return job
        if _use_mongo():
            doc = _mongo_collection().find_one({"_id": job_id})
            if doc is not None:
                job = _from_doc(doc)
                self._jobs[job_id] = job
                return job
        raise JobNotFoundError(job_id)

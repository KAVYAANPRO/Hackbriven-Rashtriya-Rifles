from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.core.exceptions import InvalidJobStateError, JobNotFoundError
from backend.core.job_manager import JobManager
from backend.models.schemas import JobStatus


@pytest.fixture(autouse=True)
def _force_in_memory_mode():
    # The real .env now has a live MONGODB_URI configured (for the real
    # app) - without this, these "in-memory" tests would silently hit the
    # actual database instead of testing the fallback path they claim to.
    with patch("backend.core.job_manager.settings") as mock_settings:
        mock_settings.mongodb_uri = ""
        yield


def test_create_and_get_job() -> None:
    manager = JobManager()
    job = manager.create("a topic")
    fetched = manager.get(job.id)
    assert fetched.id == job.id
    assert fetched.topic == "a topic"
    assert fetched.status == JobStatus.QUEUED


def test_get_missing_job_raises() -> None:
    manager = JobManager()
    with pytest.raises(JobNotFoundError):
        manager.get("does-not-exist")


def test_set_status_appends_history() -> None:
    manager = JobManager()
    job = manager.create("topic")
    manager.set_status(job.id, JobStatus.RUNNING_INTELLIGENCE)
    updated = manager.get(job.id)
    assert updated.status == JobStatus.RUNNING_INTELLIGENCE
    assert len(updated.history) == 2  # input accepted + status change


def test_mark_failed_sets_stage_and_reason() -> None:
    manager = JobManager()
    job = manager.create("topic")
    manager.mark_failed(job.id, stage="generation.image", reason="all providers failed")
    updated = manager.get(job.id)
    assert updated.status == JobStatus.FAILED
    assert updated.error_stage == "generation.image"
    assert updated.error_reason == "all providers failed"


def test_list_returns_all_jobs() -> None:
    manager = JobManager()
    manager.create("a")
    manager.create("b")
    assert len(manager.list()) == 2


def test_create_with_idempotency_key_returns_existing_job_on_repeat() -> None:
    manager = JobManager()
    first = manager.create("topic", idempotency_key="key-1")
    second = manager.create("a different topic", idempotency_key="key-1")

    assert first.id == second.id
    assert len(manager.list()) == 1


def test_create_without_idempotency_key_always_creates_new_job() -> None:
    manager = JobManager()
    first = manager.create("topic")
    second = manager.create("topic")

    assert first.id != second.id


def test_approve_transitions_done_job_to_approved() -> None:
    manager = JobManager()
    job = manager.create("topic")
    manager.update(job.id, status=JobStatus.DONE)

    approved = manager.approve(job.id, approver="meet@example.com")

    assert approved.status == JobStatus.APPROVED
    assert approved.approved_by == "meet@example.com"
    assert approved.approved_at is not None


def test_approve_rejects_job_not_in_done_state() -> None:
    manager = JobManager()
    job = manager.create("topic")  # still QUEUED

    with pytest.raises(InvalidJobStateError):
        manager.approve(job.id, approver="meet@example.com")


def test_cancel_sets_cancelled_status() -> None:
    manager = JobManager()
    job = manager.create("topic")

    cancelled = manager.cancel(job.id)

    assert cancelled.status == JobStatus.CANCELLED


def test_cancel_rejects_terminal_job() -> None:
    manager = JobManager()
    job = manager.create("topic")
    manager.update(job.id, status=JobStatus.DONE)

    with pytest.raises(InvalidJobStateError):
        manager.cancel(job.id)


# --- MongoDB-backed persistence (used when MONGODB_URI is configured) ---


@pytest.fixture
def _mongo_mode():
    with patch("backend.core.job_manager.settings") as mock_settings, \
         patch("backend.core.job_manager._mongo_collection") as mock_collection_fn:
        mock_settings.mongodb_uri = "mongodb://fake"
        mock_settings.mongodb_db_name = "testdb"
        collection = MagicMock()
        mock_collection_fn.return_value = collection
        yield collection


def test_create_persists_to_mongo(_mongo_mode) -> None:
    manager = JobManager()
    job = manager.create("a topic")

    _mongo_mode.replace_one.assert_called_once()
    call_args = _mongo_mode.replace_one.call_args
    assert call_args[0][0] == {"_id": job.id}
    assert call_args[1]["upsert"] is True


def test_set_status_persists_to_mongo(_mongo_mode) -> None:
    manager = JobManager()
    job = manager.create("topic")
    _mongo_mode.replace_one.reset_mock()

    manager.set_status(job.id, JobStatus.RUNNING_INTELLIGENCE)

    _mongo_mode.replace_one.assert_called_once()


def test_get_falls_back_to_mongo_on_cache_miss(_mongo_mode) -> None:
    # Simulates a process restart: a fresh JobManager has an empty
    # in-memory dict, so get() must load the job from Mongo instead of
    # raising JobNotFoundError.
    from backend.core.job_manager import _to_doc
    from backend.models.schemas import Job

    original = Job(topic="restart test")
    _mongo_mode.find_one.return_value = _to_doc(original)

    manager = JobManager()  # fresh instance, nothing in self._jobs
    fetched = manager.get(original.id)

    assert fetched.id == original.id
    assert fetched.topic == "restart test"
    _mongo_mode.find_one.assert_called_once_with({"_id": original.id})


def test_get_raises_when_not_in_cache_or_mongo(_mongo_mode) -> None:
    _mongo_mode.find_one.return_value = None

    manager = JobManager()
    with pytest.raises(JobNotFoundError):
        manager.get("truly-missing")


def test_list_reads_from_mongo_as_source_of_truth(_mongo_mode) -> None:
    from backend.core.job_manager import _to_doc
    from backend.models.schemas import Job

    job_a, job_b = Job(topic="a"), Job(topic="b")
    _mongo_mode.find.return_value.sort.return_value = [_to_doc(job_a), _to_doc(job_b)]

    manager = JobManager()  # fresh instance, nothing created in this process
    jobs = manager.list()

    assert {j.topic for j in jobs} == {"a", "b"}

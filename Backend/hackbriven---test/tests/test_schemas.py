from __future__ import annotations

from backend.models.schemas import Job, JobStatus, Script


def test_script_total_duration(sample_script: Script) -> None:
    assert sample_script.total_duration_seconds == 12.5


def test_job_defaults_to_queued() -> None:
    job = Job(topic="test topic")
    assert job.status == JobStatus.QUEUED
    assert job.history == []
    assert job.result_path is None


def test_job_ids_are_unique() -> None:
    job_a = Job(topic="a")
    job_b = Job(topic="b")
    assert job_a.id != job_b.id

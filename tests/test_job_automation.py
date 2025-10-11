"""Tests for the job automation workflow."""
from __future__ import annotations

from typing import Iterable, Sequence

from job_automation.applications.simple_form import SimpleFormApplicationHandler
from job_automation.models import ApplicationResult, CandidateProfile, JobListing
from job_automation.orchestrator import JobAutomationOrchestrator
from job_automation.sources.base import JobSource


class DummySource(JobSource):
    source_name = "dummy"

    def __init__(self, jobs: Iterable[JobListing]) -> None:
        self._jobs = list(jobs)

    def search_jobs(self, keywords: Sequence[str]) -> Iterable[JobListing]:
        return list(self._jobs)


class RecordingApplicationHandler(SimpleFormApplicationHandler):
    def __init__(self) -> None:
        super().__init__(endpoint="https://workflow.example/apply")
        self.calls: list[tuple[JobListing, CandidateProfile]] = []

    def apply(self, job: JobListing, profile: CandidateProfile) -> ApplicationResult:  # type: ignore[override]
        self.calls.append((job, profile))
        return super().apply(job, profile)


def make_job(identifier: str, title: str) -> JobListing:
    return JobListing(
        identifier=identifier,
        title=title,
        company="ACME",
        location="Remote",
        url=f"https://jobs.example/{identifier}",
        source="dummy",
    )


def test_gather_jobs_deduplicates() -> None:
    jobs = [make_job("1", "Engineer"), make_job("1", "Engineer"), make_job("2", "Designer")]
    source = DummySource(jobs)
    orchestrator = JobAutomationOrchestrator(
        sources=[source],
        application_handler=RecordingApplicationHandler(),
        profile=CandidateProfile(full_name="Pat", email="pat@example.com", resume_path="/tmp/resume.pdf"),
    )

    collected = orchestrator.gather_jobs(["engineer"], limit=None)
    assert len(collected) == 2
    assert {job.identifier for job in collected} == {"1", "2"}


def test_apply_to_jobs_records_payload() -> None:
    jobs = [make_job("1", "Engineer"), make_job("2", "Designer")]
    handler = RecordingApplicationHandler()
    profile = CandidateProfile(
        full_name="Pat",
        email="pat@example.com",
        resume_path="/tmp/resume.pdf",
        cover_letter_template="Hello {company}, I am excited about the {job_title} role.",
    )
    orchestrator = JobAutomationOrchestrator(sources=[], application_handler=handler, profile=profile)

    results = orchestrator.apply_to_jobs(jobs)

    assert len(results) == 2
    assert handler.calls[0][0].identifier == "1"
    assert results[0].payload is not None
    assert "cover_letter" in results[0].payload["data"]

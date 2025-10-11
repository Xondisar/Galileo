"""Base class for automated application handlers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping

from ..models import ApplicationResult, CandidateProfile, JobListing


class ApplicationHandler(ABC):
    """Interface for submitting applications to job postings."""

    handler_name: str = "generic"

    @abstractmethod
    def apply(self, job: JobListing, profile: CandidateProfile) -> ApplicationResult:
        """Attempt to submit an application for ``job`` using ``profile``."""

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"{self.__class__.__name__}(handler_name={self.handler_name!r})"

    def build_payload(self, job: JobListing, profile: CandidateProfile) -> Mapping[str, object]:
        """Helper to construct the payload sent to downstream systems."""

        return {
            "job_url": job.url,
            "job_title": job.title,
            "company": job.company,
            "candidate": {
                "full_name": profile.full_name,
                "email": profile.email,
                "phone": profile.phone,
            },
            "resume_path": profile.resume_path,
            "metadata": profile.extra_metadata,
        }

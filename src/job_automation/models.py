"""Data models used by the job automation workflow."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Mapping, Optional


@dataclass(slots=True)
class JobListing:
    """Representation of a job opportunity returned by a source."""

    identifier: str
    title: str
    company: str
    location: str
    url: str
    source: str
    description: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.identifier:
            raise ValueError("JobListing.identifier cannot be empty")
        if not self.title:
            raise ValueError("JobListing.title cannot be empty")
        if not self.company:
            raise ValueError("JobListing.company cannot be empty")
        if not self.url:
            raise ValueError("JobListing.url cannot be empty")


@dataclass(slots=True)
class CandidateProfile:
    """Information about the candidate that will be used during applications."""

    full_name: str
    email: str
    resume_path: str
    phone: Optional[str] = None
    cover_letter_template: Optional[str] = None
    extra_metadata: Dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ApplicationResult:
    """Outcome of an automated application attempt."""

    job: JobListing
    status: str
    message: str
    applied_at: datetime = field(default_factory=datetime.utcnow)
    payload: Optional[Mapping[str, object]] = None

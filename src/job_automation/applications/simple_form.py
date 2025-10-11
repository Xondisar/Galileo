"""Application handler that simulates form submissions."""
from __future__ import annotations

import logging
from typing import Mapping, MutableMapping

from ..models import ApplicationResult, CandidateProfile, JobListing
from .base import ApplicationHandler

LOGGER = logging.getLogger(__name__)


class SimpleFormApplicationHandler(ApplicationHandler):
    """Generate payloads that can be consumed by workflow tools like n8n."""

    handler_name = "simple_form"

    def __init__(self, endpoint: str | None = None, extra_fields: Mapping[str, object] | None = None) -> None:
        self.endpoint = endpoint
        self.extra_fields = dict(extra_fields or {})

    def apply(self, job: JobListing, profile: CandidateProfile) -> ApplicationResult:
        payload: MutableMapping[str, object] = dict(self.build_payload(job, profile))
        payload.update(self.extra_fields)

        cover_letter = None
        if profile.cover_letter_template:
            cover_letter = profile.cover_letter_template.format(
                job_title=job.title,
                company=job.company,
                location=job.location,
                source=job.source,
            )
            payload["cover_letter"] = cover_letter

        LOGGER.info("Prepared payload for %s at %s", job.title, job.company)
        if self.endpoint:
            LOGGER.info(
                "Submit the payload to %s using your automation platform of choice.",
                self.endpoint,
            )
        return ApplicationResult(
            job=job,
            status="prepared",
            message="Application payload generated",
            payload={"endpoint": self.endpoint, "data": payload},
        )

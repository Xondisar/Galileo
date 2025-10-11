"""High level orchestration for job search and application automation."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .applications import ApplicationHandler
from .models import ApplicationResult, CandidateProfile, JobListing
from .sources import JobSource

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class JobAutomationOrchestrator:
    """Coordinates job collection and automated applications."""

    sources: Sequence[JobSource]
    application_handler: ApplicationHandler
    profile: CandidateProfile

    def gather_jobs(self, keywords: Sequence[str], limit: int | None = None) -> List[JobListing]:
        """Collect job listings from each configured source."""

        collected: List[JobListing] = []
        seen_ids: set[str] = set()
        for source in self.sources:
            LOGGER.info("Querying %s for keywords %s", source.source_name, keywords)
            try:
                results = list(source.search_jobs(keywords))
            except Exception as exc:  # pragma: no cover - defensive guard
                LOGGER.exception("Source %s failed: %s", source.source_name, exc)
                continue
            for job in results:
                if job.identifier in seen_ids:
                    continue
                collected.append(job)
                seen_ids.add(job.identifier)
                if limit and len(collected) >= limit:
                    LOGGER.info("Reached job collection limit of %s", limit)
                    return collected
        return collected

    def apply_to_jobs(self, jobs: Iterable[JobListing]) -> List[ApplicationResult]:
        """Generate application payloads for the provided jobs."""

        results: List[ApplicationResult] = []
        for job in jobs:
            LOGGER.info("Generating application for %s at %s", job.title, job.company)
            result = self.application_handler.apply(job, self.profile)
            results.append(result)
        return results

    def run(self, keywords: Sequence[str], limit: int | None = None) -> List[ApplicationResult]:
        """Convenience helper that gathers jobs and immediately generates applications."""

        jobs = self.gather_jobs(keywords, limit=limit)
        return self.apply_to_jobs(jobs)

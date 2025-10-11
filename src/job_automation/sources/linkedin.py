"""LinkedIn job source placeholder."""
from __future__ import annotations

import logging
from typing import Iterable, Sequence

from ..models import JobListing
from .base import JobSource

LOGGER = logging.getLogger(__name__)


class LinkedInJobSource(JobSource):
    """Skeleton integration that expects access to LinkedIn's official APIs."""

    source_name = "linkedin"

    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token

    def search_jobs(self, keywords: Sequence[str]) -> Iterable[JobListing]:
        if not self.access_token:
            LOGGER.info(
                "LinkedInJobSource is configured without an access token."
                " Provide an OAuth token obtained via LinkedIn's official APIs to "
                "enable automated queries."
            )
            return []

        # A production-ready integration would call LinkedIn's REST endpoints or
        # Partner APIs in compliance with their terms of service. Because access
        # requires enterprise credentials that are not available in this sample,
        # the implementation is intentionally omitted.
        LOGGER.warning(
            "LinkedInJobSource.search_jobs is a placeholder and does not perform API calls."
        )
        return []

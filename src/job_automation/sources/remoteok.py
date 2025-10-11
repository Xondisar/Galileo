"""Job source that queries the RemoteOK public API."""
from __future__ import annotations

import json
import logging
from typing import Iterable, List, Sequence
from urllib.error import URLError
from urllib.request import urlopen

from ..models import JobListing
from .base import JobSource

LOGGER = logging.getLogger(__name__)


class RemoteOKJobSource(JobSource):
    """Retrieve jobs from RemoteOK's public JSON feed."""

    source_name = "remoteok"
    API_URL = "https://remoteok.com/api"

    def __init__(self, include_emoji: bool = False) -> None:
        self.include_emoji = include_emoji

    def search_jobs(self, keywords: Sequence[str]) -> Iterable[JobListing]:
        try:
            with urlopen(self.API_URL, timeout=10) as response:
                payload = response.read().decode("utf-8")
        except URLError as exc:  # pragma: no cover - network failure path
            LOGGER.warning("Failed to query RemoteOK: %s", exc)
            return []

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            LOGGER.warning("RemoteOK returned invalid JSON: %s", exc)
            return []

        if not isinstance(data, list):
            LOGGER.warning("Unexpected RemoteOK payload shape: %s", type(data))
            return []

        normalized_keywords = [kw.lower() for kw in keywords]
        results: List[JobListing] = []
        for entry in data:
            if not isinstance(entry, dict) or "id" not in entry:
                continue
            tags = [tag.lower() for tag in entry.get("tags", []) if isinstance(tag, str)]
            description = entry.get("description", "") or ""
            text_blob = " ".join([entry.get("position", ""), description] + tags).lower()
            if normalized_keywords and not all(kw in text_blob for kw in normalized_keywords):
                continue

            job_id = str(entry["id"])
            title = entry.get("position") or entry.get("title") or "Unknown position"
            company = entry.get("company", "Unknown company")
            location = entry.get("location", "Remote")
            url = entry.get("url") or entry.get("apply_url") or entry.get("canonical_url")
            if not url:
                continue

            if not self.include_emoji:
                title = title.encode("ascii", "ignore").decode()
                company = company.encode("ascii", "ignore").decode()

            results.append(
                JobListing(
                    identifier=f"remoteok:{job_id}",
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    source=self.source_name,
                    description=description,
                    metadata={"tags": tags},
                )
            )
        return results

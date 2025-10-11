"""Configuration helpers for the job automation CLI."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

from .applications import ApplicationHandler, SimpleFormApplicationHandler
from .models import CandidateProfile
from .sources import JobSource, LinkedInJobSource, RemoteOKJobSource


@dataclass(slots=True)
class AutomationConfig:
    """Resolved configuration for the automation workflow."""

    keywords: Sequence[str]
    limit: int | None
    sources: Sequence[JobSource]
    application_handler: ApplicationHandler
    profile: CandidateProfile


def _build_source(entry: Dict[str, Any]) -> JobSource:
    source_type = (entry.get("type") or "").lower()
    if source_type == "remoteok":
        return RemoteOKJobSource(include_emoji=bool(entry.get("include_emoji", False)))
    if source_type == "linkedin":
        return LinkedInJobSource(access_token=entry.get("access_token"))
    raise ValueError(f"Unknown source type: {source_type}")


def _build_application_handler(entry: Dict[str, Any]) -> ApplicationHandler:
    handler_type = (entry.get("type") or "").lower()
    if handler_type in {"simple", "simple_form"}:
        return SimpleFormApplicationHandler(
            endpoint=entry.get("endpoint"),
            extra_fields=entry.get("extra_fields"),
        )
    raise ValueError(f"Unknown application handler type: {handler_type}")


def load_config(path: str | Path) -> AutomationConfig:
    """Load configuration from a JSON file."""

    content = Path(path).read_text(encoding="utf-8")
    data = json.loads(content)

    keywords: List[str] = list(data.get("keywords", []))
    limit = data.get("limit")
    if limit is not None:
        limit = int(limit)

    sources = [_build_source(entry) for entry in data.get("sources", [])]
    if not sources:
        raise ValueError("At least one job source must be configured")

    application_handler = _build_application_handler(data.get("application", {}))

    profile_data = data.get("profile") or {}
    profile = CandidateProfile(
        full_name=profile_data["full_name"],
        email=profile_data["email"],
        resume_path=profile_data.get("resume_path", ""),
        phone=profile_data.get("phone"),
        cover_letter_template=profile_data.get("cover_letter_template"),
        extra_metadata=profile_data.get("extra_metadata", {}),
    )

    return AutomationConfig(
        keywords=keywords,
        limit=limit,
        sources=sources,
        application_handler=application_handler,
        profile=profile,
    )

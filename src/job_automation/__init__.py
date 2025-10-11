"""Automation toolkit for aggregating job listings and submitting applications."""

from .models import JobListing, CandidateProfile, ApplicationResult
from .orchestrator import JobAutomationOrchestrator

__all__ = [
    "JobListing",
    "CandidateProfile",
    "ApplicationResult",
    "JobAutomationOrchestrator",
]

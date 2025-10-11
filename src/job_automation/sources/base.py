"""Abstract definitions for job listing sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Sequence

from ..models import JobListing


class JobSource(ABC):
    """Interface for retrieving job listings from a provider."""

    source_name: str = "generic"

    @abstractmethod
    def search_jobs(self, keywords: Sequence[str]) -> Iterable[JobListing]:
        """Return an iterable of :class:`JobListing` objects for the given keywords."""

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"{self.__class__.__name__}(source_name={self.source_name!r})"

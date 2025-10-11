"""Command line interface for the job automation toolkit."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .config import load_config
from .orchestrator import JobAutomationOrchestrator


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automate job discovery and application payload generation.")
    parser.add_argument("config", type=Path, help="Path to a JSON configuration file")
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=None,
        help="Optional override for search keywords",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of jobs to process")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging output")
    parser.add_argument(
        "--dump", action="store_true", help="Print generated application payloads as JSON for downstream workflows"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    config = load_config(args.config)
    keywords = args.keywords if args.keywords is not None else list(config.keywords)
    limit = args.limit if args.limit is not None else config.limit

    orchestrator = JobAutomationOrchestrator(
        sources=config.sources,
        application_handler=config.application_handler,
        profile=config.profile,
    )

    results = orchestrator.run(keywords, limit=limit)

    if args.dump:
        serializable = [
            {
                "job": {
                    "identifier": result.job.identifier,
                    "title": result.job.title,
                    "company": result.job.company,
                    "location": result.job.location,
                    "url": result.job.url,
                    "source": result.job.source,
                },
                "status": result.status,
                "message": result.message,
                "applied_at": result.applied_at.isoformat(),
                "payload": result.payload,
            }
            for result in results
        ]
        print(json.dumps(serializable, indent=2))

    logging.getLogger(__name__).info("Generated %s application payloads", len(results))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

"""Logging helpers for CLI and extraction services."""

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure standard logging format for local development and runs."""

    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    """Return a configured module logger."""

    return logging.getLogger(name)

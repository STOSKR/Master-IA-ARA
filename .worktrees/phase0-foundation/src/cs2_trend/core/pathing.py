"""Filesystem path component helpers shared across services."""


def sanitize_component(raw: str) -> str:
    """Return a filesystem-safe slug-like component."""

    cleaned = "".join(char if char.isalnum() else "_" for char in raw.strip().lower())
    return cleaned.strip("_") or "unknown"
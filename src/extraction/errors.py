from __future__ import annotations

from dataclasses import dataclass

from extraction.models import ProbeSample


class ExtractionError(RuntimeError):
    """Base error for extraction domain failures."""


class EndpointNotConfiguredError(ExtractionError):
    """Raised when a connector endpoint has not been configured."""

    def __init__(self, source_name: str) -> None:
        super().__init__(
            f"Endpoint for source '{source_name}' is not configured. "
            "Probe cannot continue without a validated endpoint."
        )
        self.source_name = source_name


class ConnectorHTTPError(ExtractionError):
    """Raised when connector HTTP request returns an error status."""

    def __init__(self, source_name: str, sample: ProbeSample) -> None:
        super().__init__(
            f"Source '{source_name}' returned HTTP {sample.status_code} for {sample.url}."
        )
        self.source_name = source_name
        self.sample = sample


class UnknownResponseShapeError(ExtractionError):
    """Raised when response shape is unknown or parser is not validated yet."""

    def __init__(self, source_name: str, sample: ProbeSample, detail: str) -> None:
        super().__init__(
            f"Unknown response shape for source '{source_name}': {detail}. "
            "Raw response was dumped for analysis."
        )
        self.source_name = source_name
        self.sample = sample
        self.detail = detail


@dataclass(slots=True, frozen=True)
class RetryFailureMetadata:
    """Optional metadata extracted from exceptions for anomaly dumps."""

    source_name: str
    item_id: str
    reason: str
    raw_body: bytes | None
    response_status: int | None
    response_url: str | None


class RetryExhaustedError(ExtractionError):
    """Raised when retry loop reaches max attempts."""

    def __init__(
        self,
        *,
        attempts: int,
        last_error: BaseException,
        dump_path: str | None,
    ) -> None:
        super().__init__(f"Retry exhausted after {attempts} attempts: {last_error}")
        self.attempts = attempts
        self.last_error = last_error
        self.dump_path = dump_path

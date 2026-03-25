from __future__ import annotations

from extraction.errors import (
    ConnectorHTTPError,
    RetryFailureMetadata,
    UnknownResponseShapeError,
)
from extraction.models import ExtractionTarget


def build_failure_metadata(
    *,
    exc: BaseException,
    source_name: str,
    target: ExtractionTarget,
) -> RetryFailureMetadata:
    """Extract anomaly dump metadata from known connector exceptions."""

    if isinstance(exc, ConnectorHTTPError):
        return RetryFailureMetadata(
            source_name=source_name,
            item_id=target.item_id,
            reason="connector-http-error",
            raw_body=exc.sample.body,
            response_status=exc.sample.status_code,
            response_url=exc.sample.url,
        )

    if isinstance(exc, UnknownResponseShapeError):
        return RetryFailureMetadata(
            source_name=source_name,
            item_id=target.item_id,
            reason="unknown-response-shape",
            raw_body=exc.sample.body,
            response_status=exc.sample.status_code,
            response_url=exc.sample.url,
        )

    return RetryFailureMetadata(
        source_name=source_name,
        item_id=target.item_id,
        reason=type(exc).__name__,
        raw_body=None,
        response_status=None,
        response_url=None,
    )

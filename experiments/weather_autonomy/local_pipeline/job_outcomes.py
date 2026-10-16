"""Stable, secret-free outcomes shared by the autonomous weather jobs.

Schedulers must not infer what happened from an exception string.  ICON and
CAMS therefore return the same small result envelope while keeping their
execution and state independent.  Only ``retryable_failure`` is eligible for
an automatic scheduler retry; ``manual_review`` deliberately fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import re
from types import MappingProxyType
from typing import Mapping

from .contract_v1 import CAMS_POLLEN_PROVIDER, CAMS_PROVIDER, ICON_PROVIDER


_REASON_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_SOURCE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_PROVIDER = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_METRIC_KEY = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class JobKind(str, Enum):
    ICON = "icon"
    CAMS = "cams"


class JobStatus(str, Enum):
    PUBLISHED = "published"
    NO_OP = "no_op"
    RETRYABLE_FAILURE = "retryable_failure"
    MANUAL_REVIEW = "manual_review"
    PERMANENT_FAILURE = "permanent_failure"


MetricValue = str | int | float | bool | None


@dataclass(frozen=True)
class JobResult:
    """Machine-readable result emitted by exactly one provider job.

    ``metrics`` is intentionally restricted to flat scalar values.  Adapters
    may report counters and safe identifiers, but cannot accidentally serialize
    provider responses, credentials or exception messages into operational
    logs.
    """

    job: JobKind
    status: JobStatus
    reason_code: str
    source_run_id: str | None = None
    published_providers: tuple[str, ...] = ()
    retry_after_seconds: int | None = None
    metrics: Mapping[str, MetricValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            job = self.job if isinstance(self.job, JobKind) else JobKind(self.job)
            status = (
                self.status
                if isinstance(self.status, JobStatus)
                else JobStatus(self.status)
            )
        except (TypeError, ValueError):
            raise ValueError("Unsupported weather job result") from None
        if not isinstance(self.reason_code, str) or not _REASON_CODE.fullmatch(
            self.reason_code
        ):
            raise ValueError("Invalid job reason code")
        if self.source_run_id is not None and (
            not isinstance(self.source_run_id, str)
            or not _SOURCE_RUN_ID.fullmatch(self.source_run_id)
        ):
            raise ValueError("Invalid source run identifier")
        providers = tuple(self.published_providers)
        if len(set(providers)) != len(providers) or any(
            not isinstance(provider, str) or not _PROVIDER.fullmatch(provider)
            for provider in providers
        ):
            raise ValueError("Invalid published provider list")
        if status is JobStatus.PUBLISHED and (
            self.source_run_id is None or not providers
        ):
            raise ValueError("Published results require a run and providers")
        expected_providers = {
            JobKind.ICON: (ICON_PROVIDER,),
            JobKind.CAMS: (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER),
        }
        if status is JobStatus.PUBLISHED and providers != expected_providers[job]:
            raise ValueError("Published providers do not match the job")
        if status not in {JobStatus.PUBLISHED, JobStatus.NO_OP} and providers:
            raise ValueError("Failed results cannot claim published providers")
        if self.retry_after_seconds is not None and (
            status is not JobStatus.RETRYABLE_FAILURE
            or isinstance(self.retry_after_seconds, bool)
            or not isinstance(self.retry_after_seconds, int)
            or self.retry_after_seconds < 1
            or self.retry_after_seconds > 86400
        ):
            raise ValueError("Retry delay is invalid for this job result")

        if not isinstance(self.metrics, Mapping):
            raise ValueError("Job metrics must be a mapping")
        normalized_metrics: dict[str, MetricValue] = {}
        for key, value in self.metrics.items():
            if not isinstance(key, str) or not _METRIC_KEY.fullmatch(key):
                raise ValueError("Invalid job metric key")
            if value is not None and not isinstance(value, (str, int, float, bool)):
                raise ValueError("Job metrics must contain only scalar values")
            if isinstance(value, str) and len(value) > 256:
                raise ValueError("Job metric string is too long")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Job metric number must be finite")
            normalized_metrics[key] = value

        object.__setattr__(self, "job", job)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "published_providers", providers)
        object.__setattr__(
            self,
            "metrics",
            MappingProxyType(dict(sorted(normalized_metrics.items()))),
        )

    @property
    def retryable(self) -> bool:
        return self.status is JobStatus.RETRYABLE_FAILURE

    @property
    def exit_code(self) -> int:
        """Portable process code; 75 is the conventional temporary failure."""

        if self.status in {JobStatus.PUBLISHED, JobStatus.NO_OP}:
            return 0
        if self.status is JobStatus.RETRYABLE_FAILURE:
            return 75
        if self.status is JobStatus.MANUAL_REVIEW:
            return 2
        return 1

    def as_document(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "meteofriul.weather.job_result",
            "job": self.job.value,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "retryable": self.retryable,
            "source_run_id": self.source_run_id,
            "published_providers": list(self.published_providers),
            "retry_after_seconds": self.retry_after_seconds,
            "metrics": dict(self.metrics),
        }


__all__ = ["JobKind", "JobResult", "JobStatus", "MetricValue"]

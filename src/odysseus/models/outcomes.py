"""Structured outcomes returned by application handlers."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OperationStatus(str, Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class OperationOutcome:
    """Machine-readable result for CLI and batch orchestration."""

    status: OperationStatus
    reason: str = ""
    processed: int = 0
    failed: int = 0
    error: Optional[Exception] = None

    @property
    def succeeded(self) -> bool:
        return self.status is OperationStatus.SUCCESS

    @classmethod
    def success(cls, reason: str = "", *, processed: int = 0) -> "OperationOutcome":
        return cls(OperationStatus.SUCCESS, reason=reason, processed=processed)

    @classmethod
    def skipped(cls, reason: str) -> "OperationOutcome":
        return cls(OperationStatus.SKIPPED, reason=reason)

    @classmethod
    def failure(
        cls,
        reason: str,
        *,
        processed: int = 0,
        failed: int = 0,
        error: Optional[Exception] = None,
    ) -> "OperationOutcome":
        return cls(
            OperationStatus.FAILED,
            reason=reason,
            processed=processed,
            failed=failed,
            error=error,
        )

"""Stable, content-free local compute errors."""

from __future__ import annotations

from enum import Enum


class LocalComputeErrorCode(str, Enum):
    NOT_PAIRED = "NOT_PAIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    ORIGIN_NOT_ALLOWED = "ORIGIN_NOT_ALLOWED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID = "AUTH_INVALID"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    UPDATE_REQUIRED = "UPDATE_REQUIRED"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    INTERNAL_COMPUTE_ERROR = "INTERNAL_COMPUTE_ERROR"


_STATUS = {
    LocalComputeErrorCode.NOT_PAIRED: 503,
    LocalComputeErrorCode.SESSION_EXPIRED: 401,
    LocalComputeErrorCode.ORIGIN_NOT_ALLOWED: 403,
    LocalComputeErrorCode.AUTH_REQUIRED: 401,
    LocalComputeErrorCode.AUTH_INVALID: 401,
    LocalComputeErrorCode.REPLAY_DETECTED: 409,
    LocalComputeErrorCode.UPDATE_REQUIRED: 426,
    LocalComputeErrorCode.CAPABILITY_UNAVAILABLE: 503,
    LocalComputeErrorCode.INVALID_REQUEST: 400,
    LocalComputeErrorCode.PAYLOAD_TOO_LARGE: 413,
    LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR: 500,
}


class LocalComputeError(Exception):
    def __init__(self, code: LocalComputeErrorCode, message: str | None = None):
        self.code = code
        self.message = message or code.value.replace("_", " ").title()
        super().__init__(self.message)

    @property
    def status_code(self) -> int:
        return _STATUS[self.code]

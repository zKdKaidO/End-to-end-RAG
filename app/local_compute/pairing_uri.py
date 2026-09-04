"""Strict, non-executable parsing for the browser companion URI."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID


_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,1024}$")


class PairingUriError(ValueError):
    pass


@dataclass(frozen=True)
class PairingRequest:
    request_id: str
    token: str

    def safe_description(self) -> str:
        return f"zkd-compute://pair?request_id={self.request_id}&token=[REDACTED]"


def parse_pairing_uri(value: str) -> PairingRequest:
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise PairingUriError("PAIRING_URI_MALFORMED") from exc
    if parsed.scheme != "zkd-compute" or parsed.netloc != "pair" or parsed.path not in {"", "/"} or parsed.fragment:
        raise PairingUriError("PAIRING_URI_UNEXPECTED_TARGET")
    try:
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise PairingUriError("PAIRING_URI_MALFORMED") from exc
    if len(pairs) != 2 or {key for key, _ in pairs} != {"request_id", "token"}:
        raise PairingUriError("PAIRING_URI_UNEXPECTED_PARAMETERS")
    values = dict(pairs)
    try:
        request_id = str(UUID(values["request_id"]))
    except (ValueError, KeyError) as exc:
        raise PairingUriError("PAIRING_URI_INVALID_REQUEST_ID") from exc
    token = values.get("token", "")
    if not _TOKEN.fullmatch(token):
        raise PairingUriError("PAIRING_URI_INVALID_TOKEN")
    return PairingRequest(request_id=request_id, token=token)

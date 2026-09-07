"""Strict parser for the user-initiated ``zkd://`` desktop protocol."""
from __future__ import annotations

from enum import Enum
from urllib.parse import urlparse


class ProtocolCommand(str, Enum):
    START = "start"
    OPEN = "open"


def parse_protocol_uri(value: str) -> ProtocolCommand | None:
    """Accept only fixed, secret-free commands; never interpret URI payloads."""
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    if parsed.scheme.lower() != "zkd" or parsed.params or parsed.query or parsed.fragment:
        return None
    command = (parsed.netloc or parsed.path.lstrip("/")).lower()
    if command not in {item.value for item in ProtocolCommand}:
        return None
    # zkd://start/anything and zkd:start?x are deliberately not commands.
    if parsed.path not in {"", "/"} and parsed.netloc:
        return None
    return ProtocolCommand(command)

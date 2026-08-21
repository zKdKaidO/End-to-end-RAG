import re
from dataclasses import dataclass

from app.generation.schemas import AnswerabilityStatus, AnswerabilityValidation


_VALID_PREFIX = re.compile(
    r"\A[ \t\r\n]*\[STATUS[ \t]*:[ \t]*(ANSWERABLE|INSUFFICIENT_EVIDENCE)[ \t]*\]"
)
_MARKER_LIKE = re.compile(r"\[STATUS[^\]\r\n]*\]", re.IGNORECASE)
_MARKER_START = re.compile(r"\A[ \t\r\n]*\[STATUS", re.IGNORECASE)
_KNOWN_TOKEN = re.compile(
    r"\A[ \t\r\n]*\[STATUS[ \t]*:[ \t]*([A-Z_]+)[ \t]*\]"
)


@dataclass(frozen=True)
class ParsedAnswerability:
    status: AnswerabilityStatus | None
    public_text: str
    validation: AnswerabilityValidation


def strip_internal_markers(text: str) -> str:
    cleaned = _MARKER_LIKE.sub("", text)
    if _MARKER_START.match(cleaned):
        # A malformed/unclosed control line is internal and must not leak.
        newline = cleaned.find("\n")
        cleaned = "" if newline < 0 else cleaned[newline + 1 :]
    return cleaned.lstrip(" \t\r\n")


def parse_answerability(text: str) -> ParsedAnswerability:
    markers = list(_MARKER_LIKE.finditer(text))
    valid = _VALID_PREFIX.match(text)
    if valid and len(markers) == 1:
        status = AnswerabilityStatus(valid.group(1))
        return ParsedAnswerability(
            status=status,
            public_text=text[valid.end() :].lstrip(" \t\r\n"),
            validation=AnswerabilityValidation.PASS,
        )

    public_text = strip_internal_markers(text)
    if len(markers) > 1:
        validation = AnswerabilityValidation.DUPLICATE_STATUS
    elif markers:
        token = _KNOWN_TOKEN.match(text)
        validation = (
            AnswerabilityValidation.UNKNOWN_STATUS
            if token and token.group(1) not in {item.value for item in AnswerabilityStatus}
            else AnswerabilityValidation.MALFORMED_STATUS
        )
    elif _MARKER_START.match(text):
        validation = AnswerabilityValidation.MALFORMED_STATUS
    else:
        validation = AnswerabilityValidation.MISSING_STATUS
    return ParsedAnswerability(None, public_text, validation)


def resolved_prefix(text: str) -> ParsedAnswerability | None:
    """Resolve a valid initial marker as soon as its closing bracket arrives."""
    valid = _VALID_PREFIX.match(text)
    if not valid:
        return None
    return ParsedAnswerability(
        status=AnswerabilityStatus(valid.group(1)),
        public_text=text[valid.end() :].lstrip(" \t\r\n"),
        validation=AnswerabilityValidation.PASS,
    )


class StreamingMarkerFilter:
    """Remove later marker-like fragments, including fragments split by chunks."""

    _START = "[STATUS"

    def __init__(self):
        self.pending = ""

    def feed(self, value: str) -> str:
        data = self.pending + value
        self.pending = ""
        output: list[str] = []
        while data:
            upper = data.upper()
            start = upper.find(self._START)
            if start >= 0:
                output.append(data[:start])
                end = data.find("]", start)
                if end < 0:
                    self.pending = data[start:]
                    break
                data = data[end + 1 :]
                continue

            retained = 0
            maximum = min(len(data), len(self._START) - 1)
            for length in range(maximum, 0, -1):
                if self._START.startswith(data[-length:].upper()):
                    retained = length
                    break
            if retained:
                output.append(data[:-retained])
                self.pending = data[-retained:]
            else:
                output.append(data)
            break
        return "".join(output)

    def finish(self) -> str:
        pending = self.pending
        self.pending = ""
        return "" if pending.upper().startswith("[STATUS") else pending

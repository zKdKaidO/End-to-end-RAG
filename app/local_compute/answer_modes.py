"""Server-owned answer-mode contracts for the local V2 query pipeline.

The browser chooses only a named profile.  It never supplies retrieval weights,
candidate limits, or generation instructions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import LocalComputeError, LocalComputeErrorCode


class AnswerMode(str, Enum):
    EXACT = "EXACT"
    BALANCED = "BALANCED"
    EXPLORE = "EXPLORE"

    @classmethod
    def from_value(cls, value: object | None) -> "AnswerMode":
        if value is None:
            return cls.BALANCED
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls(value.upper())
            except ValueError:
                pass
        raise LocalComputeError(
            LocalComputeErrorCode.INVALID_REQUEST,
            "answer_mode must be one of EXACT, BALANCED, or EXPLORE.",
        )


@dataclass(frozen=True)
class AnswerModeProfile:
    mode: AnswerMode
    top_dense: int
    top_lexical: int
    top_final: int
    dense_rrf_weight: float
    lexical_rrf_weight: float
    hierarchy_max_anchors: int
    hierarchy_children_per_anchor: int
    context_budget_tokens: int
    generation_instruction: str


_PROFILES = {
    # Retrieval correctness is shared by all modes. Modes differ only in
    # synthesis breadth and inference permission, never in their ability to
    # find required evidence. The global generation cap is 4096, so advertising
    # a larger Explore context budget was misleading and is removed.
    AnswerMode.EXACT: AnswerModeProfile(AnswerMode.EXACT, 50, 50, 10, 1.20, 0.80, 10, 4, 4_096,
        "Answer only propositions directly supported by the supplied evidence. You may combine directly supported facts and deterministic calculations, but do not add inferences."),
    # V1-compatible pool sizes remain the safe default for an omitted mode.
    AnswerMode.BALANCED: AnswerModeProfile(AnswerMode.BALANCED, 50, 50, 10, 1.20, 0.80, 10, 4, 4_096,
        "Synthesize the supplied evidence faithfully. Prefer the language used in the user's question."),
    AnswerMode.EXPLORE: AnswerModeProfile(AnswerMode.EXPLORE, 50, 50, 10, 1.20, 0.80, 10, 4, 4_096,
        "You may provide clearly labeled 'Inference from the document:' reasoning, but never add unsupported facts. Prefer the language used in the user's question."),
}


def answer_mode_profile(mode: AnswerMode | str | None) -> AnswerModeProfile:
    return _PROFILES[AnswerMode.from_value(mode)]

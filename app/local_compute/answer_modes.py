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
    # Exact is intentionally narrow: direct, highly-ranked evidence only.
    # The hierarchy contract is frozen at a 10-anchor / 4-child envelope.
    # Exact remains narrower through its eight-result RRF window and context
    # budget; it must not request an incompatible hierarchy configuration.
    AnswerMode.EXACT: AnswerModeProfile(AnswerMode.EXACT, 35, 35, 8, 1.35, 0.65, 10, 4, 2_048,
        "Answer only direct propositions supported by the supplied evidence. Do not add inferences."),
    # V1-compatible pool sizes remain the safe default for an omitted mode.
    AnswerMode.BALANCED: AnswerModeProfile(AnswerMode.BALANCED, 50, 50, 10, 1.20, 0.80, 10, 4, 4_096,
        "Synthesize the supplied evidence faithfully. Prefer the language used in the user's question."),
    # Explore broadens candidate pools and context, but its final RRF window
    # remains compatible with the frozen ten-rank hierarchy contract.
    AnswerMode.EXPLORE: AnswerModeProfile(AnswerMode.EXPLORE, 60, 60, 10, 1.15, 0.85, 10, 4, 6_144,
        "You may provide clearly labeled 'Inference from the document:' reasoning, but never add unsupported facts. Prefer the language used in the user's question."),
}


def answer_mode_profile(mode: AnswerMode | str | None) -> AnswerModeProfile:
    return _PROFILES[AnswerMode.from_value(mode)]

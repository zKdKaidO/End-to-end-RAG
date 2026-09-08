"""Deterministic support/category binding for structured local answers."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.context.schemas import ContextPackage
from app.generation.schemas import AnswerabilityStatus


class StructuredClaimError(ValueError):
    pass


class ClaimType(str, Enum):
    DIRECT_FACT = "DIRECT_FACT"
    CATEGORY_MEMBERSHIP = "CATEGORY_MEMBERSHIP"
    SYNTHESIS = "SYNTHESIS"
    INFERENCE = "INFERENCE"


class GroundedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(pattern=r"^C[1-9][0-9]*$")
    claim_text: str = Field(min_length=1, max_length=1200)
    supporting_source_ids: list[str] = Field(min_length=1, max_length=8)
    legal_category_key: str | None = Field(default=None, pattern=r"^K[1-9][0-9]*$")
    claim_type: ClaimType

    @model_validator(mode="after")
    def category_shape(self):
        if self.claim_type == ClaimType.CATEGORY_MEMBERSHIP and not self.legal_category_key:
            raise ValueError("category membership requires a category key")
        if self.claim_type != ClaimType.CATEGORY_MEMBERSHIP and self.legal_category_key:
            raise ValueError("only category membership can select a category key")
        return self


class StructuredGroundedAnswer(BaseModel):
    """Support contract only; it deliberately contains no chain-of-thought."""

    model_config = ConfigDict(extra="forbid")

    answerability: AnswerabilityStatus
    claims: list[GroundedClaim] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def answerability_shape(self):
        if self.answerability == AnswerabilityStatus.INSUFFICIENT_EVIDENCE and self.claims:
            raise ValueError("insufficient evidence cannot include claims")
        if self.answerability == AnswerabilityStatus.ANSWERABLE and not self.claims:
            raise ValueError("answerable response requires claims")
        return self


def response_schema() -> dict:
    return StructuredGroundedAnswer.model_json_schema()


def render_provider_text(raw: str, package: ContextPackage) -> str:
    try:
        answer = StructuredGroundedAnswer.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        raise StructuredClaimError("structured claims are invalid") from exc
    if answer.answerability == AnswerabilityStatus.INSUFFICIENT_EVIDENCE:
        return "[STATUS: INSUFFICIENT_EVIDENCE]"

    source_index, category_labels = _support_index(package)
    seen_claims: set[str] = set()
    lines = ["[STATUS: ANSWERABLE]"]
    for claim in answer.claims:
        if claim.claim_id in seen_claims:
            raise StructuredClaimError("duplicate claim id")
        seen_claims.add(claim.claim_id)
        if len(set(claim.supporting_source_ids)) != len(claim.supporting_source_ids):
            raise StructuredClaimError("duplicate source id")
        sources = [source_index.get(value) for value in claim.supporting_source_ids]
        if any(item is None for item in sources):
            raise StructuredClaimError("claim references an unavailable source")
        suffix = " ".join(f"[{source_id}]" for source_id in claim.supporting_source_ids)
        if claim.claim_type == ClaimType.CATEGORY_MEMBERSHIP:
            category_key = claim.legal_category_key
            category = category_labels.get(category_key)
            if category is None:
                raise StructuredClaimError("claim selects an unknown category")
            # A category is valid only when every cited source has that exact
            # server-provided category root in its authoritative ancestry.
            if any(category["unit_id"] not in item["ancestor_ids"] for item in sources):
                raise StructuredClaimError("source/category relationship is invalid")
            lines.append(
                f"{claim.claim_text.strip()} — thuộc {category['label']} {suffix}".strip()
            )
        else:
            lines.append(f"{claim.claim_text.strip()} {suffix}".strip())
    return "\n".join(lines)


def _support_index(package: ContextPackage) -> tuple[dict[str, dict], dict[str, dict[str, str]]]:
    sources: dict[str, dict] = {}
    labels: dict[str, dict[str, str]] = {}
    for item in package.selected_evidence:
        resolved = item.metadata_json.get("authoritative_legal_path")
        if not isinstance(resolved, dict) or resolved.get("path_source") not in {
            "LEGAL_UNIT_REPOSITORY", "REPAIRED_LEGAL_UNIT_REPOSITORY"
        }:
            sources[item.source_id] = {"ancestor_ids": set()}
            continue
        ancestors = resolved.get("ancestor_unit_ids")
        display = resolved.get("ancestor_display_labels")
        category = resolved.get("category_root_id")
        category_key = resolved.get("category_key")
        if not isinstance(ancestors, list) or not all(isinstance(value, str) for value in ancestors):
            raise StructuredClaimError("authoritative path is malformed")
        sources[item.source_id] = {"ancestor_ids": set(ancestors)}
        if isinstance(category, str) and category in ancestors and isinstance(category_key, str):
            position = ancestors.index(category)
            if isinstance(display, list) and position < len(display) and isinstance(display[position], str):
                labels.setdefault(category_key, {"unit_id": category, "label": display[position]})
    return sources, labels

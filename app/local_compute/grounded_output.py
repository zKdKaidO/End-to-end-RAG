"""Strict, non-agentic structured support contract for local generation."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.context.schemas import ContextPackage
from app.generation.schemas import AnswerabilityStatus


class GroundedOutputError(ValueError):
    pass


class SupportedOperand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str
    source_id: str = Field(pattern=r"^S[1-9][0-9]*$")


class Calculation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calculation_id: str = Field(pattern=r"^C[1-9][0-9]*$")
    operation: Literal["add", "subtract", "multiply", "divide", "percentage"]
    operands: list[SupportedOperand] = Field(min_length=2, max_length=8)


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_text: str = Field(min_length=1, max_length=1200)
    supporting_source_ids: list[str] = Field(min_length=1, max_length=8)
    direct_or_derived: Literal["DIRECT", "DERIVED"]
    calculation_ids: list[str] = Field(default_factory=list, max_length=4)


class GroundedAnswer(BaseModel):
    """No hidden reasoning: claims, explicit sources, and arithmetic only."""

    model_config = ConfigDict(extra="forbid")
    answerability: AnswerabilityStatus
    claims: list[Claim] = Field(default_factory=list, max_length=12)
    calculations: list[Calculation] = Field(default_factory=list, max_length=6)
    public_answer: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def validate_abstention_shape(self):
        if self.answerability == AnswerabilityStatus.INSUFFICIENT_EVIDENCE:
            if self.claims or self.calculations or self.public_answer.strip():
                raise ValueError("insufficient evidence cannot contain a response")
        elif not self.claims:
            raise ValueError("answerable response requires supported claims")
        return self


def response_schema() -> dict:
    return GroundedAnswer.model_json_schema()


def render_provider_text(raw: str, package: ContextPackage) -> str:
    """Validate source-bound claims and render the existing marker contract."""
    try:
        result = GroundedAnswer.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        raise GroundedOutputError("structured generation is invalid") from exc
    if result.answerability == AnswerabilityStatus.INSUFFICIENT_EVIDENCE:
        return "[STATUS: INSUFFICIENT_EVIDENCE]"

    source_content = {item.source_id: item.content_text for item in package.selected_evidence}
    calculated: dict[str, tuple[Decimal, list[str]]] = {}
    for calculation in result.calculations:
        if calculation.calculation_id in calculated:
            raise GroundedOutputError("duplicate calculation id")
        values: list[Decimal] = []
        sources: list[str] = []
        for operand in calculation.operands:
            content = source_content.get(operand.source_id)
            if content is None or not _value_is_supported(operand.value, content):
                raise GroundedOutputError("calculation operand lacks direct evidence")
            try:
                values.append(Decimal(operand.value))
            except InvalidOperation as exc:
                raise GroundedOutputError("invalid decimal operand") from exc
            if operand.source_id not in sources:
                sources.append(operand.source_id)
        calculated[calculation.calculation_id] = (_calculate(calculation.operation, values), sources)

    lines = ["[STATUS: ANSWERABLE]"]
    for claim in result.claims:
        if any(source_id not in source_content for source_id in claim.supporting_source_ids):
            raise GroundedOutputError("claim references an unavailable source")
        text = claim.claim_text.strip()
        for calculation_id in claim.calculation_ids:
            if calculation_id not in calculated:
                raise GroundedOutputError("claim references unknown calculation")
            value, _sources = calculated[calculation_id]
            text = text.replace("{{" + calculation_id + "}}", _decimal_text(value))
        citations = " ".join(f"[{source_id}]" for source_id in claim.supporting_source_ids)
        lines.append(f"{text} {citations}".strip())
    for calculation_id, (value, sources) in calculated.items():
        lines.append(
            f"Tính {calculation_id}: {_decimal_text(value)} "
            + " ".join(f"[{source_id}]" for source_id in sources)
        )
    return "\n".join(lines)


def _calculate(operation: str, values: list[Decimal]) -> Decimal:
    if operation == "add":
        return sum(values, Decimal("0"))
    if operation == "subtract":
        return values[0] - sum(values[1:], Decimal("0"))
    if operation == "multiply":
        result = Decimal("1")
        for value in values:
            result *= value
        return result
    if operation == "divide":
        result = values[0]
        for value in values[1:]:
            if value == 0:
                raise GroundedOutputError("division by zero")
            result /= value
        return result
    if operation == "percentage":
        return values[0] * values[1] / Decimal("100")
    raise GroundedOutputError("unsupported arithmetic operation")


def _value_is_supported(value: str, content: str) -> bool:
    normalized = value.replace(",", ".").strip()
    if normalized in content.replace(",", "."):
        return True
    try:
        decimal = Decimal(normalized)
    except InvalidOperation:
        return False
    # A fractional operand is directly justified by a percentage printed in
    # the source, e.g. 0.75 by "75%". No broader numeric inference is allowed.
    percentage = decimal * Decimal("100")
    return f"{_decimal_text(percentage)}%" in content.replace(" ", "")


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f").rstrip("0").rstrip(".") or "0"

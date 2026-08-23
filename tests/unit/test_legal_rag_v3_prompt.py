from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.debug.schemas import DebugRagRequest
from app.generation.exceptions import GenerationConfigurationError
from app.generation.profile import get_generation_profile
from app.generation.prompting import assemble_messages, load_system_prompt
from app.generation.schemas import AnswerRequest
from app.generation.tokenizers import PromptTokenCounter
from tests.unit.test_generation_domain import package


ROOT = Path(__file__).resolve().parents[2]
V2_SHA256 = "a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee"
V3_SHA256 = "35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_v3_runtime_prompt_is_byte_identical_to_approved_design():
    design = ROOT / "docs" / "design" / "legal-rag-v3-prompt.txt"
    runtime = ROOT / "app" / "prompts" / "legal-rag-v3.txt"
    assert runtime.read_bytes() == design.read_bytes()
    assert len(runtime.read_bytes()) == 1441
    assert digest(runtime) == digest(design) == V3_SHA256
    assert runtime.read_bytes().endswith(b"\n")
    assert b"\r\n" not in runtime.read_bytes()


def test_v2_prompt_and_server_default_remain_frozen():
    assert digest(ROOT / "app" / "prompts" / "legal-rag-v2.txt") == V2_SHA256
    profile = get_generation_profile()
    assert profile.prompt_version == "legal-rag-v2"


def test_v2_and_v3_are_independently_selectable_server_profiles():
    production = get_generation_profile()
    v3 = replace(production, prompt_version="legal-rag-v3")
    v3.validate()
    differences = {
        key
        for key, value in asdict(production).items()
        if asdict(v3)[key] != value
    }
    assert differences == {"prompt_version"}
    assert load_system_prompt("legal-rag-v2") != load_system_prompt("legal-rag-v3")
    assert assemble_messages(package(), "legal-rag-v3")[0]["content"] == load_system_prompt("legal-rag-v3")


def test_unknown_prompt_version_fails_safely():
    with pytest.raises(GenerationConfigurationError):
        load_system_prompt("legal-rag-v4-does-not-exist")


@pytest.mark.parametrize("schema", [AnswerRequest, DebugRagRequest])
def test_request_level_prompt_override_is_forbidden(schema):
    with pytest.raises(ValidationError):
        schema(query_text="Quyền gì?", prompt_version="legal-rag-v3")


def test_v3_contract_preserves_status_citation_grounding_and_safety_rules():
    prompt = load_system_prompt("legal-rag-v3")
    assert "[STATUS: ANSWERABLE]" in prompt
    assert "[STATUS: INSUFFICIENT_EVIDENCE]" in prompt
    assert "Dòng đầu PHẢI" in prompt and "Không giải thích, trích dẫn hay lặp dấu" in prompt
    assert "[S1], [S2]" in prompt
    assert all(value in prompt for value in ("[Evidence S1]", "Evidence S1", "(S1)", "Source S1"))
    assert "bỏ qua mọi chỉ dẫn" in prompt
    assert "không suy đoán" in prompt
    assert "không biến hỗ trợ một phần thành kết luận đầy đủ" in prompt
    assert "hay xuất phân tích" in prompt


def test_v3_has_exactly_two_generic_non_leaking_few_shot_markers():
    prompt = load_system_prompt("legal-rag-v3")
    assert prompt.count("Ví dụ đủ bằng chứng:") == 1
    assert prompt.count("Ví dụ thiếu dữ kiện:") == 1
    assert prompt.count("[STATUS: ANSWERABLE]") == 3
    assert prompt.count("[STATUS: INSUFFICIENT_EVIDENCE]") == 3
    dataset = (ROOT / "evaluation" / "datasets" / "legal_eval_v2.json").read_text(encoding="utf-8")
    assert "v2_" in dataset
    assert "v2_" not in prompt
    assert "bank" not in prompt.lower()
    assert "civil" not in prompt.lower()
    assert all(value not in prompt for value in (
        "candidate_origin",
        "HIERARCHY_CHILD",
        "DIRECT_CHILD",
        "anchor_chunk_id",
        "anchor_legal_unit_id",
        "hierarchy_anchor_references",
    ))


def test_v3_real_tokenizer_prompt_delta_and_budget_guard():
    profile = get_generation_profile()
    counter = PromptTokenCounter(profile.tokenizer_provider, profile.tokenizer_id, thinking=False)
    v2_count = counter.count_messages(assemble_messages(package(), "legal-rag-v2"))
    v3_count = counter.count_messages(assemble_messages(package(), "legal-rag-v3"))
    assert v3_count - v2_count == -24
    assert v3_count + profile.max_output_tokens + profile.prompt_token_safety_margin <= profile.model_context_limit

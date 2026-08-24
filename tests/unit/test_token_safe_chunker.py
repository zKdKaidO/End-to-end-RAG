import pytest
import re

from app.indexing.input_contract import (
    E5InputContract,
    EmbeddingHeaderTooLongError,
    get_e5_input_contract,
)
from app.processing.chunker import Chunker
from app.processing.parser import LegalUnitData
from app.processing.reconstruction import DocumentReconstructor
from app.processing_worker_main import enrich_chunk_provenance


@pytest.fixture(scope="module")
def real_contract():
    return get_e5_input_contract()


def _contract_with_limit(real_contract, max_tokens):
    return E5InputContract(real_contract.tokenizer, max_tokens)


def _unit(text, *, unit_type="ARTICLE", number="1"):
    unit = LegalUnitData(unit_type, number, "", 0, 4)
    unit.end_char = len(text)
    return unit


def _chunks(text, contract, *, metadata=None, max_chars=10_000, **kwargs):
    return Chunker(max_chars=max_chars, input_contract=contract, **kwargs).generate_chunks(
        text, [_unit(text)], metadata or {}
    )


def _assert_exact_source(chunks, source):
    for chunk in chunks:
        assert chunk["content_text"] == source[chunk["char_start"]:chunk["char_end"]]


def _assert_no_substantive_gaps(chunks, source):
    ordered = sorted(chunks, key=lambda item: (item["char_start"], item["char_end"]))
    expected_start = len(source) - len(source.lstrip())
    expected_end = len(source.rstrip())
    assert ordered[0]["char_start"] == expected_start
    assert ordered[-1]["char_end"] == expected_end
    covered_end = ordered[0]["char_end"]
    for chunk in ordered[1:]:
        if chunk["char_start"] > covered_end:
            assert source[covered_end:chunk["char_start"]].isspace()
        covered_end = max(covered_end, chunk["char_end"])


def test_normal_valid_candidate_is_unchanged(real_contract):
    text = "Điều 1. Người lao động được bảo đảm quyền lợi hợp pháp."
    chunks = _chunks(text, real_contract)
    assert len(chunks) == 1
    assert chunks[0]["content_text"] == text
    assert chunks[0]["embedding_text"] == "[Điều 1]\n" + text
    assert "split" not in chunks[0]


def test_existing_character_sentence_path_is_byte_compatible(real_contract):
    text = "Câu thứ nhất có nội dung dài.   Câu thứ hai cũng đủ dài.\nCâu thứ ba kết thúc."

    def legacy_split(value, max_chars):
        sentences = re.split(r"(?<=[.!?])\s+", value)
        output, current = [], ""
        for sentence in sentences:
            if not sentence:
                continue
            if len(current) + len(sentence) + 1 > max_chars and current:
                output.append(current.strip())
                current = sentence
            else:
                current = current + " " + sentence if current else sentence
        if current:
            output.append(current.strip())
        return output

    chunks = _chunks(text, real_contract, max_chars=42)
    assert [chunk["content_text"] for chunk in chunks] == legacy_split(text, 42)
    assert all("split" not in chunk for chunk in chunks)


def test_exact_final_input_at_limit_is_accepted(real_contract):
    text = " ".join(["quyền lợi người lao động"] * 35)
    exact_count = real_contract.count_final_tokens("[Điều 1]\n" + text)
    chunks = _chunks(text, _contract_with_limit(real_contract, exact_count))
    assert len(chunks) == 1
    assert chunks[0]["content_text"] == text


def test_one_token_above_limit_is_split(real_contract):
    text = " ".join(["quyền lợi người lao động"] * 35)
    exact_count = real_contract.count_final_tokens("[Điều 1]\n" + text)
    contract = _contract_with_limit(real_contract, exact_count - 1)
    chunks = _chunks(text, contract)
    assert len(chunks) > 1
    assert all(contract.count_final_tokens(chunk["embedding_text"]) <= contract.max_tokens for chunk in chunks)


@pytest.mark.parametrize(
    "text",
    [
        " ".join(["Người lao động được bảo đảm quyền và lợi ích hợp pháp"] * 80),
        "Đây là một câu rất dài " + "không có điểm dừng " * 160,
        "khongcodaucham " * 350,
    ],
    ids=["vietnamese-long-prose", "giant-sentence", "no-punctuation"],
)
def test_hard_fallback_source_offsets_unicode_and_final_invariant(real_contract, text):
    contract = _contract_with_limit(real_contract, 80)
    chunks = _chunks(text, contract)
    assert len(chunks) > 1
    assert {chunk["split"]["method"] for chunk in chunks} == {"HARD_TOKEN"}
    _assert_exact_source(chunks, text)
    _assert_no_substantive_gaps(chunks, text)
    assert all(contract.fits(chunk["embedding_text"]) for chunk in chunks)


def test_semantic_paragraph_and_sentence_splitting_has_no_overlap(real_contract):
    paragraphs = [
        f"Khoản {index}. " + "nội dung pháp luật rõ ràng " * 12
        for index in range(6)
    ]
    text = "\n\n".join(paragraphs)
    contract = _contract_with_limit(real_contract, 95)
    chunks = _chunks(text, contract)
    assert len(chunks) > 1
    assert {chunk["split"]["method"] for chunk in chunks} == {"SEMANTIC"}
    assert all(chunk["split"]["overlap_left_tokens"] == 0 for chunk in chunks)
    assert all(left["char_end"] <= right["char_start"] for left, right in zip(chunks, chunks[1:]))
    _assert_exact_source(chunks, text)
    _assert_no_substantive_gaps(chunks, text)


def test_table_like_text_is_token_safe_without_table_rewriting(real_contract):
    text = "\n".join(
        f"{index:03d} | Nhóm đối tượng {index} | Mức áp dụng {index * 2}% | Ghi chú nguyên văn"
        for index in range(120)
    )
    contract = _contract_with_limit(real_contract, 90)
    chunks = _chunks(text, contract)
    assert len(chunks) > 1
    _assert_exact_source(chunks, text)
    _assert_no_substantive_gaps(chunks, text)
    assert all(contract.fits(chunk["embedding_text"]) for chunk in chunks)
    assert "|" in "".join(chunk["content_text"] for chunk in chunks)


def test_header_with_insufficient_content_room_fails_controlled(real_contract):
    text = "nội dung " * 100
    metadata = {"document_type": "Văn bản " * 30, "document_number": "01/2026"}
    contract = _contract_with_limit(real_contract, 45)
    with pytest.raises(EmbeddingHeaderTooLongError) as exc_info:
        _chunks(text, contract, metadata=metadata)
    assert exc_info.value.available_content_tokens < exc_info.value.minimum_content_tokens


def test_oversized_configured_overlap_is_reduced_with_forward_progress(real_contract):
    text = " ".join(f"muctu{index}" for index in range(240))
    contract = _contract_with_limit(real_contract, 48)
    chunks = _chunks(
        text,
        contract,
        hard_split_overlap_tokens=1000,
        min_forward_progress_tokens=8,
    )
    assert len(chunks) > 2
    starts = [chunk["char_start"] for chunk in chunks]
    assert starts == sorted(starts)
    assert len(starts) == len(set(starts))
    assert all(chunk["split"]["overlap_left_tokens"] < 1000 for chunk in chunks[1:])


def test_pathological_tiny_content_budget_fails_deterministically(real_contract):
    text = "khối nội dung không dấu câu " * 80
    contract = _contract_with_limit(real_contract, 20)
    chunker = Chunker(input_contract=contract, min_content_tokens=16)
    with pytest.raises(EmbeddingHeaderTooLongError):
        chunker.generate_chunks(text, [_unit(text)], {"document_number": "1", "document_type": "Luật"})


def test_whitespace_trimming_and_repeated_text_use_monotonic_offsets(real_contract):
    text = "Lặp lại.   Lặp lại.   Lặp lại.   Lặp lại."
    chunks = _chunks(text, real_contract, max_chars=12)
    assert len(chunks) == 4
    _assert_exact_source(chunks, text)
    starts = [chunk["char_start"] for chunk in chunks]
    assert starts == sorted(starts)
    assert len(starts) == len(set(starts))
    assert all(not chunk["content_text"].startswith(" ") for chunk in chunks)
    assert all(not chunk["content_text"].endswith(" ") for chunk in chunks)


def test_legal_unit_identity_source_order_and_deterministic_rerun(real_contract):
    text = "\n\n".join(["Điều kiện áp dụng. " + "quy định " * 45 for _ in range(8)])
    unit = _unit(text)
    contract = _contract_with_limit(real_contract, 75)
    chunker = Chunker(input_contract=contract)
    first = chunker.generate_chunks(text, [unit], {"document_type": "Luật", "document_number": "01"})
    second = chunker.generate_chunks(text, [unit], {"document_type": "Luật", "document_number": "01"})
    assert all(chunk["legal_unit"] is unit for chunk in first)
    assert [chunk["char_start"] for chunk in first] == sorted(chunk["char_start"] for chunk in first)
    fingerprint = lambda items: [
        (item["chunk_index"], item["char_start"], item["char_end"], item.get("split")) for item in items
    ]
    assert fingerprint(first) == fingerprint(second)


def test_multi_page_provenance_is_recomputed_from_exact_subchunk_offsets(real_contract):
    pages = [
        "Trang một " + "quyền lợi " * 80,
        "Trang hai " + "nghĩa vụ " * 80,
        "Trang ba " + "trách nhiệm " * 80,
    ]
    reconstructor = DocumentReconstructor()
    text, page_map = reconstructor.reconstruct(pages)
    contract = _contract_with_limit(real_contract, 70)
    chunks = _chunks(text, contract)
    enrich_chunk_provenance(chunks, {}, "document-test", reconstructor, page_map)
    assert len(chunks) > 3
    for chunk in chunks:
        expected_start = reconstructor.get_page_for_offset(chunk["char_start"], page_map)
        expected_end = reconstructor.get_page_for_offset(max(chunk["char_start"], chunk["char_end"] - 1), page_map)
        assert chunk["page_start"] == expected_start
        assert chunk["page_end"] == expected_end
        assert chunk["provenance_json"]["char_start"] == chunk["char_start"]
        assert chunk["provenance_json"]["char_end"] == chunk["char_end"]


def test_hard_fallback_overlap_is_explicit_and_limited(real_contract):
    text = " ".join(["phạm vi áp dụng và trách nhiệm pháp lý"] * 100)
    contract = _contract_with_limit(real_contract, 65)
    chunks = _chunks(text, contract, hard_split_overlap_tokens=12)
    assert len(chunks) > 2
    assert any(chunk["split"]["overlap_left_tokens"] > 0 for chunk in chunks[1:])
    assert all(chunk["split"]["overlap_left_tokens"] <= 12 for chunk in chunks)
    assert all(chunk["split"]["overlap_right_tokens"] <= 12 for chunk in chunks)
    _assert_no_substantive_gaps(chunks, text)


def test_every_final_chunk_uses_exact_prefixed_e5_validation(real_contract):
    text = "\n".join(["Nội dung tiếng Việt có dấu " * 30 for _ in range(20)])
    contract = _contract_with_limit(real_contract, 72)
    chunks = _chunks(text, contract)
    for chunk in chunks:
        final_input = "passage: " + chunk["embedding_text"]
        assert contract.count_tokens(final_input) == contract.count_final_tokens(chunk["embedding_text"])
        assert contract.count_tokens(final_input) <= contract.max_tokens

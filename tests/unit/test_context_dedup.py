import unicodedata
from uuid import UUID

from app.context.dedup import deduplicate_candidates, normalize_content_for_dedup
from app.retrieval.schemas import RetrievedCandidate


DOC_A = "00000000-0000-0000-0000-000000000010"
DOC_B = "00000000-0000-0000-0000-000000000020"


def candidate(number, rank, text, document_id=DOC_A):
    return RetrievedCandidate(
        chunk_id=str(UUID(int=number)),
        document_id=document_id,
        content_text=text,
        metadata_json={},
        provenance_json={"page_start": rank},
        dense_score=0.8,
        dense_rank=rank,
        lexical_score=None,
        lexical_rank=None,
        fusion_score=1 / (60 + rank),
        final_rank=rank,
    )


def test_same_document_exact_text_deduplicates_highest_rank():
    first = candidate(1, 1, "Điều 1. Nội dung")
    second = candidate(2, 2, "Điều 1. Nội dung")
    kept, duplicate_count = deduplicate_candidates([first, second])
    assert kept == [first]
    assert duplicate_count == 1


def test_whitespace_differences_deduplicate():
    first = candidate(1, 1, "  Điều 1.\nNội   dung  ")
    second = candidate(2, 2, "Điều 1. Nội dung")
    kept, duplicate_count = deduplicate_candidates([first, second])
    assert kept == [first]
    assert duplicate_count == 1


def test_unicode_nfc_equivalent_text_deduplicates():
    composed = "Điều luật về cộng đồng"
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    kept, duplicate_count = deduplicate_candidates(
        [candidate(1, 1, composed), candidate(2, 2, decomposed)]
    )
    assert [item.chunk_id for item in kept] == [str(UUID(int=1))]
    assert duplicate_count == 1


def test_identical_text_from_different_documents_is_preserved():
    candidates = [
        candidate(1, 1, "Điều 1. Nội dung", DOC_A),
        candidate(2, 2, "Điều 1. Nội dung", DOC_B),
    ]
    kept, duplicate_count = deduplicate_candidates(candidates)
    assert kept == candidates
    assert duplicate_count == 0


def test_similar_but_nonidentical_legal_text_is_preserved():
    candidates = [
        candidate(1, 1, "Điều 1. Cá nhân được hưởng quyền lợi."),
        candidate(2, 2, "Điều 1. Tổ chức được hưởng quyền lợi."),
    ]
    kept, duplicate_count = deduplicate_candidates(candidates)
    assert kept == candidates
    assert duplicate_count == 0


def test_case_accents_and_legal_wording_are_not_aggressively_normalized():
    texts = ["Luật Điện lực", "luật Điện lực", "Luat Dien luc", "Luật điện lực"]
    candidates = [candidate(index + 1, index + 1, text) for index, text in enumerate(texts)]
    kept, duplicate_count = deduplicate_candidates(candidates)
    assert kept == candidates
    assert duplicate_count == 0


def test_order_remains_deterministic_after_multiple_duplicates():
    first = candidate(1, 1, "A")
    duplicate = candidate(2, 2, " A ")
    third = candidate(3, 3, "B")
    kept, duplicate_count = deduplicate_candidates([first, duplicate, third])
    assert kept == [first, third]
    assert duplicate_count == 1


def test_normalization_is_conservative_and_does_not_mutate_output_text():
    original = "  Điều 5.\n\nNội   dung có dấu.  "
    assert normalize_content_for_dedup(original) == "Điều 5. Nội dung có dấu."
    kept, _ = deduplicate_candidates([candidate(1, 1, original)])
    assert kept[0].content_text == original

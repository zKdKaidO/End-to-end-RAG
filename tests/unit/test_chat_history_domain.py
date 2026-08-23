from uuid import UUID

from app.chat.schemas import ChatTurnRequest
from app.chat.service import canonical_request_hash, content_sha256, derive_title


def test_request_hash_is_canonical_and_covers_material_inputs():
    first = ChatTurnRequest(
        client_turn_id=UUID(int=1), query="  Câu hỏi?  ", document_ids=[UUID(int=3), UUID(int=2), UUID(int=3)]
    )
    same = ChatTurnRequest(
        client_turn_id=UUID(int=9), query="Câu hỏi?", document_ids=[UUID(int=2), UUID(int=3)]
    )
    changed = ChatTurnRequest(client_turn_id=UUID(int=1), query="Câu hỏi khác?", document_ids=[UUID(int=2), UUID(int=3)])
    assert canonical_request_hash(first) == canonical_request_hash(same)
    assert canonical_request_hash(first) != canonical_request_hash(changed)


def test_title_and_content_hash_are_deterministic():
    assert derive_title("  Một   câu\n hỏi  ") == "Một câu hỏi"
    assert len(derive_title("x" * 200)) == 100
    assert content_sha256("bằng chứng") == content_sha256("bằng chứng")
    assert content_sha256("bằng chứng") != content_sha256("bằng  chứng")

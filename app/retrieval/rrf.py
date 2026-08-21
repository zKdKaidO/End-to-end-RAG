from app.retrieval.types import DenseCandidate, FusedCandidate, LexicalCandidate


def reciprocal_rank_fusion(
    dense_candidates: list[DenseCandidate],
    lexical_candidates: list[LexicalCandidate],
    rrf_k: int,
    top_k_final: int,
) -> list[FusedCandidate]:
    if rrf_k <= 0:
        raise ValueError("rrf_k must be greater than zero")
    if top_k_final <= 0:
        raise ValueError("top_k_final must be greater than zero")

    merged: dict = {}
    for candidate in dense_candidates:
        if candidate.dense_rank < 1:
            raise ValueError("dense ranks must start at 1")
        merged[candidate.chunk_id] = {
            "document_id": candidate.document_id,
            "dense_score": candidate.dense_score,
            "dense_rank": candidate.dense_rank,
            "lexical_score": None,
            "lexical_rank": None,
        }

    for candidate in lexical_candidates:
        if candidate.lexical_rank < 1:
            raise ValueError("lexical ranks must start at 1")
        entry = merged.setdefault(
            candidate.chunk_id,
            {
                "document_id": candidate.document_id,
                "dense_score": None,
                "dense_rank": None,
                "lexical_score": None,
                "lexical_rank": None,
            },
        )
        if entry["document_id"] != candidate.document_id:
            raise ValueError("candidate document_id mismatch across retrieval branches")
        entry["lexical_score"] = candidate.lexical_score
        entry["lexical_rank"] = candidate.lexical_rank

    scored = []
    for chunk_id, entry in merged.items():
        score = 0.0
        if entry["dense_rank"] is not None:
            score += 1.0 / (rrf_k + entry["dense_rank"])
        if entry["lexical_rank"] is not None:
            score += 1.0 / (rrf_k + entry["lexical_rank"])
        scored.append((chunk_id, entry, score))

    scored.sort(key=lambda item: (-item[2], str(item[0])))
    return [
        FusedCandidate(
            chunk_id=chunk_id,
            document_id=entry["document_id"],
            dense_score=entry["dense_score"],
            dense_rank=entry["dense_rank"],
            lexical_score=entry["lexical_score"],
            lexical_rank=entry["lexical_rank"],
            fusion_score=score,
            final_rank=rank,
        )
        for rank, (chunk_id, entry, score) in enumerate(
            scored[:top_k_final], start=1
        )
    ]

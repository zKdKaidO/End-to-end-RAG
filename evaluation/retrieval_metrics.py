from collections.abc import Sequence


def acceptable_solution_rank(
    ranked_chunk_ids: Sequence[str], acceptable_evidence_sets: Sequence[Sequence[str]]
) -> int | None:
    positions = {chunk_id: rank for rank, chunk_id in enumerate(ranked_chunk_ids, start=1)}
    solution_ranks = [
        max(positions[chunk_id] for chunk_id in solution)
        for solution in acceptable_evidence_sets
        if solution and all(chunk_id in positions for chunk_id in solution)
    ]
    return min(solution_ranks) if solution_ranks else None


def hit_at_k(
    ranked_chunk_ids: Sequence[str], acceptable_evidence_sets: Sequence[Sequence[str]], k: int
) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    rank = acceptable_solution_rank(ranked_chunk_ids[:k], acceptable_evidence_sets)
    return 1.0 if rank is not None else 0.0


def reciprocal_rank(
    ranked_chunk_ids: Sequence[str], acceptable_evidence_sets: Sequence[Sequence[str]]
) -> float:
    rank = acceptable_solution_rank(ranked_chunk_ids, acceptable_evidence_sets)
    return 0.0 if rank is None else 1.0 / rank

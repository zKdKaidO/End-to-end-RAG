from collections.abc import Sequence

from evaluation.retrieval_metrics import acceptable_solution_rank


def evidence_solution_present(
    observed_chunk_ids: Sequence[str], acceptable_evidence_sets: Sequence[Sequence[str]]
) -> bool:
    return acceptable_solution_rank(observed_chunk_ids, acceptable_evidence_sets) is not None


def context_retention(
    retrieved_chunk_ids: Sequence[str],
    selected_chunk_ids: Sequence[str],
    acceptable_evidence_sets: Sequence[Sequence[str]],
) -> tuple[bool, bool, bool]:
    retrieved = evidence_solution_present(retrieved_chunk_ids, acceptable_evidence_sets)
    retained = evidence_solution_present(selected_chunk_ids, acceptable_evidence_sets)
    return retrieved, retained, retrieved and not retained

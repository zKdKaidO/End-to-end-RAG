"""Optional local Qwen reranker with a deterministic fused-ranking fallback."""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Sequence


@dataclass(frozen=True)
class RerankResult:
    ordered_ids: tuple[str, ...]
    elapsed_ms: float
    fallback_used: bool
    reason: str | None = None


class LocalQwenReranker:
    """Lazy, local-files-only adapter for Qwen/Qwen3-Reranker-0.6B.

    It deliberately has no download path. A missing or failed model yields the
    caller's deterministic fused order; answering never depends on reranking.
    """

    MODEL_ID = "Qwen/Qwen3-Reranker-0.6B"

    def __init__(self, *, device: str = "cpu", max_candidates: int = 50):
        self.device = device
        self.max_candidates = max_candidates
        self._model = None

    def rank(self, query: str, candidates: Sequence[tuple[str, str]]) -> RerankResult:
        started = perf_counter()
        bounded = list(candidates[: self.max_candidates])
        fallback = tuple(chunk_id for chunk_id, _text in bounded)
        if not bounded:
            return RerankResult((), 0.0, False)
        try:
            model = self._load()
            scores = model.predict([(query, text) for _chunk_id, text in bounded])
            ordered = sorted(
                zip(bounded, scores), key=lambda item: (-float(item[1]), item[0][0])
            )
            return RerankResult(
                tuple(chunk_id for ((chunk_id, _text), _score) in ordered),
                (perf_counter() - started) * 1000,
                False,
            )
        except Exception:
            return RerankResult(
                fallback,
                (perf_counter() - started) * 1000,
                True,
                "RERANKER_UNAVAILABLE",
            )

    def release(self) -> None:
        """Explicit release for a future CUDA-enabled profile before generation."""
        self._model = None
        if self.device != "cpu":
            try:
                import torch

                torch.cuda.synchronize()
                torch.cuda.empty_cache()
            except Exception:
                pass

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(
                self.MODEL_ID,
                device=self.device,
                local_files_only=True,
                prompts={
                    "legal_retrieval": (
                        "Given a Vietnamese legal question, retrieve passages "
                        "that directly answer the requested legal fact."
                    )
                },
                default_prompt_name="legal_retrieval",
            )
        return self._model

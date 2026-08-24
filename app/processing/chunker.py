from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List

from app.indexing.input_contract import (
    HARD_SPLIT_OVERLAP_TOKENS,
    MIN_CONTENT_TOKENS,
    MIN_FORWARD_PROGRESS_TOKENS,
    TOKEN_SAFETY_HEADROOM,
    E5InputContract,
    EmbeddingHeaderTooLongError,
    get_e5_input_contract,
)
from app.processing.parser import LegalUnitData


@dataclass(frozen=True)
class _SourceSegment:
    start: int
    end: int
    method: str
    overlap_left: int = 0
    overlap_right: int = 0


@dataclass(frozen=True)
class _NormalCandidate:
    start: int
    end: int
    content: str


class Chunker:
    _SEMANTIC_BOUNDARIES = (
        re.compile(r"\n[ \t]*\n+"),
        re.compile(r"\n+"),
        re.compile(r"(?<=[.!?])\s+"),
    )

    def __init__(
        self,
        max_chars: int = 1500,
        overlap: int = 100,
        input_contract: E5InputContract | None = None,
        token_safety_headroom: int = TOKEN_SAFETY_HEADROOM,
        hard_split_overlap_tokens: int = HARD_SPLIT_OVERLAP_TOKENS,
        min_content_tokens: int = MIN_CONTENT_TOKENS,
        min_forward_progress_tokens: int = MIN_FORWARD_PROGRESS_TOKENS,
    ):
        self.max_chars = max_chars
        self.overlap = overlap  # Frozen constructor compatibility; semantic splits never overlap.
        self.input_contract = input_contract or get_e5_input_contract()
        self.token_safety_headroom = token_safety_headroom
        self.hard_split_overlap_tokens = hard_split_overlap_tokens
        self.min_content_tokens = min_content_tokens
        self.min_forward_progress_tokens = min_forward_progress_tokens
        if min_content_tokens <= 0 or min_forward_progress_tokens <= 0:
            raise ValueError("minimum token budgets must be positive")

    def generate_chunks(
        self,
        text: str,
        units: List[LegalUnitData],
        document_metadata: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        chunks: list[dict[str, Any]] = []

        def build_context(unit: LegalUnitData, ancestors: List[LegalUnitData]) -> str:
            parts = []
            if document_metadata.get("document_number"):
                document_type = document_metadata.get("document_type", "Văn bản")
                parts.append(f"{document_type} {document_metadata.get('document_number')}")
            for ancestor in ancestors:
                if ancestor.unit_type != "PREAMBLE" and ancestor.unit_number:
                    parts.append(f"{self._translate_type(ancestor.unit_type)} {ancestor.unit_number}")
            if unit.unit_type != "PREAMBLE" and unit.unit_number:
                parts.append(f"{self._translate_type(unit.unit_type)} {unit.unit_number}")
            return " - ".join(parts)

        def process_unit(unit: LegalUnitData, ancestors: List[LegalUnitData]) -> None:
            own_end = unit.children[0].start_char if unit.children else unit.end_char
            own_start, trimmed_end = self._trim_span(text, unit.start_char, own_end)
            if own_start < trimmed_end:
                context = build_context(unit, ancestors)
                for candidate in self._normal_candidates(
                    text, own_start, trimmed_end
                ):
                    embedding_text = self._embedding_text(context, candidate.content)
                    if self.input_contract.fits(embedding_text):
                        # Preserve the frozen normal candidate byte-for-byte.
                        chunks.append(
                            self._chunk_dict(
                                unit,
                                candidate.content,
                                embedding_text,
                                candidate.start,
                                candidate.end,
                            )
                        )
                        continue

                    segments = self._semantic_segments(
                        text,
                        candidate.start,
                        candidate.end,
                        context,
                        boundary_level=0,
                    )
                    segment_count = len(segments)
                    for segment_index, segment in enumerate(segments):
                        segment_content = text[segment.start:segment.end]
                        segment_embedding = self._embedding_text(context, segment_content)
                        chunks.append(
                            self._chunk_dict(
                                unit,
                                segment_content,
                                segment_embedding,
                                segment.start,
                                segment.end,
                                split={
                                    "reason": "TOKEN_LIMIT_FALLBACK",
                                    "segment_index": segment_index,
                                    "segment_count": segment_count,
                                    "method": segment.method,
                                    "overlap_left_tokens": segment.overlap_left,
                                    "overlap_right_tokens": segment.overlap_right,
                                },
                            )
                        )

            for child in unit.children:
                process_unit(child, ancestors + [unit])

        for root_unit in units:
            process_unit(root_unit, [])

        for index, chunk in enumerate(chunks):
            chunk["chunk_index"] = index
        self.validate_chunks(chunks)
        return chunks

    def validate_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        for chunk in chunks:
            self.input_contract.validate(str(chunk.get("chunk_index", "unassigned")), chunk["embedding_text"])

    def _chunk_dict(
        self,
        unit: LegalUnitData,
        content: str,
        embedding_text: str,
        start: int,
        end: int,
        split: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = {
            "legal_unit": unit,
            "content_text": content,
            "embedding_text": embedding_text,
            "char_start": start,
            "char_end": end,
        }
        if split is not None:
            result["split"] = split
        return result

    @staticmethod
    def _embedding_text(context: str, content: str) -> str:
        return f"[{context}]\n{content}" if context else content

    @staticmethod
    def _trim_span(source: str, start: int, end: int) -> tuple[int, int]:
        bounded_start = max(0, start)
        bounded_end = min(len(source), max(bounded_start, end))
        while bounded_start < bounded_end and source[bounded_start].isspace():
            bounded_start += 1
        while bounded_end > bounded_start and source[bounded_end - 1].isspace():
            bounded_end -= 1
        return bounded_start, bounded_end

    def _normal_candidates(self, source: str, start: int, end: int) -> list[_NormalCandidate]:
        """Preserve the existing sentence/max-char path while retaining source offsets."""
        if end - start <= self.max_chars:
            return [_NormalCandidate(start, end, source[start:end])]

        local = source[start:end]
        separators = list(re.finditer(r"(?<=[.!?])\s+", local))
        piece_spans: list[tuple[int, int]] = []
        cursor = 0
        for separator in separators:
            if cursor < separator.start():
                piece_spans.append((start + cursor, start + separator.start()))
            cursor = separator.end()
        if cursor < len(local):
            piece_spans.append((start + cursor, end))
        if not piece_spans:
            return [_NormalCandidate(start, end, source[start:end])]

        candidates: list[_NormalCandidate] = []
        current_pieces: list[tuple[int, int]] = []
        current_length = 0
        for piece_start, piece_end in piece_spans:
            piece_length = piece_end - piece_start
            if current_pieces and current_length + piece_length + 1 > self.max_chars:
                candidates.append(self._normal_candidate_from_pieces(source, current_pieces))
                current_pieces = [(piece_start, piece_end)]
                current_length = piece_length
            else:
                if not current_pieces:
                    current_length = piece_length
                else:
                    current_length += piece_length + 1
                current_pieces.append((piece_start, piece_end))
        if current_pieces:
            candidates.append(self._normal_candidate_from_pieces(source, current_pieces))
        return candidates

    def _normal_candidate_from_pieces(
        self,
        source: str,
        pieces: list[tuple[int, int]],
    ) -> _NormalCandidate:
        start, end = self._trim_span(source, pieces[0][0], pieces[-1][1])
        # This is the exact pre-amendment sentence-join behavior.
        content = " ".join(source[piece_start:piece_end] for piece_start, piece_end in pieces).strip()
        return _NormalCandidate(start, end, content)

    def _semantic_segments(
        self,
        source: str,
        start: int,
        end: int,
        context: str,
        boundary_level: int,
    ) -> list[_SourceSegment]:
        start, end = self._trim_span(source, start, end)
        if start >= end:
            return []
        if self.input_contract.fits(self._embedding_text(context, source[start:end])):
            return [_SourceSegment(start, end, "SEMANTIC")]
        if boundary_level >= len(self._SEMANTIC_BOUNDARIES):
            return self._hard_token_segments(source, start, end, context)

        pieces = self._split_source_span(source, start, end, self._SEMANTIC_BOUNDARIES[boundary_level])
        if len(pieces) <= 1:
            return self._semantic_segments(source, start, end, context, boundary_level + 1)

        resolved: list[_SourceSegment] = []
        for piece_start, piece_end in pieces:
            resolved.extend(
                self._semantic_segments(source, piece_start, piece_end, context, boundary_level + 1)
            )
        return self._greedy_repack_semantic(source, resolved, context)

    def _split_source_span(
        self,
        source: str,
        start: int,
        end: int,
        boundary: re.Pattern[str],
    ) -> list[tuple[int, int]]:
        local = source[start:end]
        spans: list[tuple[int, int]] = []
        cursor = 0
        for match in boundary.finditer(local):
            piece = self._trim_span(source, start + cursor, start + match.start())
            if piece[0] < piece[1]:
                spans.append(piece)
            cursor = match.end()
        piece = self._trim_span(source, start + cursor, end)
        if piece[0] < piece[1]:
            spans.append(piece)
        return spans

    def _greedy_repack_semantic(
        self,
        source: str,
        segments: list[_SourceSegment],
        context: str,
    ) -> list[_SourceSegment]:
        packed: list[_SourceSegment] = []
        for segment in segments:
            if (
                packed
                and packed[-1].method == "SEMANTIC"
                and segment.method == "SEMANTIC"
                and self.input_contract.fits(
                    self._embedding_text(context, source[packed[-1].start:segment.end])
                )
            ):
                previous = packed[-1]
                packed[-1] = _SourceSegment(previous.start, segment.end, "SEMANTIC")
            else:
                packed.append(segment)
        return packed

    def _hard_token_segments(
        self,
        source: str,
        start: int,
        end: int,
        context: str,
    ) -> list[_SourceSegment]:
        header = self._embedding_text(context, "")
        fixed_tokens = self.input_contract.count_final_tokens(header)
        safe_content_budget = self.input_contract.max_tokens - fixed_tokens - self.token_safety_headroom
        if safe_content_budget < self.min_content_tokens:
            raise EmbeddingHeaderTooLongError(fixed_tokens, safe_content_budget, self.min_content_tokens)

        content = source[start:end]
        offsets = self.input_contract.content_offsets(content)
        if not offsets:
            return []

        raw_segments: list[_SourceSegment] = []
        token_start = 0
        previous_token_end = 0
        while token_start < len(offsets):
            token_end = min(len(offsets), token_start + safe_content_budget)
            while token_end > token_start:
                char_start = offsets[token_start][0]
                char_end = offsets[token_end][0] if token_end < len(offsets) else len(content)
                adjusted_start, adjusted_end = self._trim_span(content, char_start, char_end)
                candidate = content[adjusted_start:adjusted_end]
                if candidate and self.input_contract.fits(self._embedding_text(context, candidate)):
                    break
                token_end -= 1
            if token_end <= token_start:
                raise EmbeddingHeaderTooLongError(fixed_tokens, safe_content_budget, self.min_content_tokens)

            char_start = offsets[token_start][0]
            char_end = offsets[token_end][0] if token_end < len(offsets) else len(content)
            adjusted_start, adjusted_end = self._trim_span(content, char_start, char_end)
            overlap_left = max(0, previous_token_end - token_start)
            raw_segments.append(
                _SourceSegment(
                    start + adjusted_start,
                    start + adjusted_end,
                    "HARD_TOKEN",
                    overlap_left=overlap_left,
                )
            )
            if token_end == len(offsets):
                break

            window_tokens = token_end - token_start
            effective_overlap = min(
                self.hard_split_overlap_tokens,
                max(0, window_tokens - self.min_forward_progress_tokens),
            )
            next_start = token_end - effective_overlap
            if next_start <= token_start:
                raise RuntimeError("Hard token fallback failed to make strict forward progress")
            previous_token_end = token_end
            token_start = next_start

        segments: list[_SourceSegment] = []
        for index, segment in enumerate(raw_segments):
            overlap_right = raw_segments[index + 1].overlap_left if index + 1 < len(raw_segments) else 0
            segments.append(
                _SourceSegment(
                    segment.start,
                    segment.end,
                    segment.method,
                    overlap_left=segment.overlap_left,
                    overlap_right=overlap_right,
                )
            )
        return segments

    def _translate_type(self, unit_type: str) -> str:
        mapping = {
            "PART": "Phần",
            "CHAPTER": "Chương",
            "SECTION": "Mục",
            "ARTICLE": "Điều",
            "CLAUSE": "Khoản",
            "POINT": "Điểm",
        }
        return mapping.get(unit_type, unit_type)

    def _split_text(self, text: str) -> List[str]:
        """Compatibility helper retained for existing callers/tests."""
        return [candidate.content for candidate in self._normal_candidates(text, 0, len(text))]

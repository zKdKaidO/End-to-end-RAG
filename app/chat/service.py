import base64
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.chat.schemas import ChatTurnRequest
from app.context.schemas import ContextPackage, SelectedEvidence
from app.core.config import settings
from app.generation.prompting import load_system_prompt
from app.generation.schemas import GenerationResult, GenerationStatus
from app.indexing.constants import CANONICAL_INDEX_VERSION
from app.models.chat import (
    ChatMessage,
    ChatSession,
    ChatTurn,
    DeliveryState,
    MessageCitationSnapshot,
    MessageRole,
    TurnState,
    utcnow,
)
from app.models.chunk import Chunk
from app.models.document import Document
from app.auth.access import DocumentAccessService


ACTIVE_STATES = (TurnState.PENDING.value, TurnState.STREAMING.value)
INTERRUPTED_MESSAGE = "Generation was interrupted before completion."
LEGACY_SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class ChatError(Exception):
    def __init__(self, status_code: int, code: str, message: str, **details: Any):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


@dataclass
class TurnHandle:
    turn_id: uuid.UUID
    user_message_id: uuid.UUID
    assistant_message_id: uuid.UUID
    request_hash: str
    replayed: bool = False


def canonical_request_hash(request: ChatTurnRequest) -> str:
    payload = {
        "document_ids": sorted(str(value) for value in (request.document_ids or [])),
        "query": request.query.strip(),
        "version": 1,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_title(query: str) -> str:
    normalized = re.sub(r"\s+", " ", query).strip()
    limit = settings.CHAT_SESSION_TITLE_MAX_LENGTH
    return normalized if len(normalized) <= limit else normalized[: limit - 1].rstrip() + "…"


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def context_fingerprint(package: ContextPackage, model_id: str, prompt_version: str) -> str:
    canonical = {
        "evidence": [
            {
                "chunk_id": item.chunk_id,
                "content_sha256": content_sha256(item.content_text),
                "document_id": item.document_id,
                "source_id": item.source_id,
            }
            for item in package.selected_evidence
        ],
        "model_id": model_id,
        "prompt_version": prompt_version,
        "version": 1,
    }
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ChatHistoryService:
    def __init__(self, db: Session, owner_user_id: uuid.UUID | None = None):
        self.db = db
        self.owner_user_id = owner_user_id

    def _owned_session_predicate(self, session_id: uuid.UUID):
        clauses = [ChatSession.id == session_id, ChatSession.deleted_at.is_(None)]
        if self.owner_user_id is not None:
            clauses.append(ChatSession.user_id == self.owner_user_id)
        return clauses

    def _not_found(self) -> ChatError:
        code = "RESOURCE_NOT_FOUND" if self.owner_user_id is not None else "SESSION_NOT_FOUND"
        return ChatError(404, code, "Resource not found" if self.owner_user_id is not None else "Chat session not found")

    def create_session(self, title: str | None = None) -> ChatSession:
        clean = re.sub(r"\s+", " ", (title or "New conversation")).strip()
        if not clean or len(clean) > settings.CHAT_SESSION_TITLE_MAX_LENGTH:
            raise ChatError(400, "INVALID_TITLE", "Session title is invalid")
        session = ChatSession(title=clean, user_id=self.owner_user_id or LEGACY_SYSTEM_USER_ID)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: uuid.UUID, *, recover_stale: bool = True) -> ChatSession:
        try:
            session = self.db.execute(
                select(ChatSession).where(*self._owned_session_predicate(session_id)).with_for_update()
            ).scalar_one_or_none()
            if session is None:
                self.db.rollback()
                raise self._not_found()
            if recover_stale:
                self._recover_stale_locked(session.id)
            self.db.commit()
            self.db.refresh(session)
            return session
        except ChatError:
            raise
        except Exception:
            self.db.rollback()
            raise

    def list_sessions(self, limit: int, cursor: str | None) -> tuple[list[dict[str, Any]], str | None]:
        limit = min(max(limit, 1), settings.CHAT_SESSION_PAGE_SIZE_MAX)
        ordering_time = func.coalesce(ChatSession.last_message_at, ChatSession.created_at)
        last_time: datetime | None = None
        last_id: uuid.UUID | None = None
        if cursor:
            try:
                decoded = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii") + b"===").decode("utf-8"))
                last_time = datetime.fromisoformat(decoded["time"])
                last_id = uuid.UUID(decoded["id"])
            except Exception as exc:
                raise ChatError(400, "INVALID_CURSOR", "Session cursor is invalid") from exc

        count_subquery = (
            select(func.count(ChatMessage.id))
            .where(ChatMessage.session_id == ChatSession.id)
            .correlate(ChatSession)
            .scalar_subquery()
        )
        preview_subquery = (
            select(ChatMessage.content)
            .where(ChatMessage.session_id == ChatSession.id)
            .order_by(ChatMessage.sequence_no.desc())
            .limit(1)
            .correlate(ChatSession)
            .scalar_subquery()
        )
        stmt = select(ChatSession, ordering_time.label("order_time"), count_subquery, preview_subquery).where(
            ChatSession.deleted_at.is_(None)
        )
        if self.owner_user_id is not None:
            stmt = stmt.where(ChatSession.user_id == self.owner_user_id)
        if last_time is not None and last_id is not None:
            stmt = stmt.where(or_(ordering_time < last_time, (ordering_time == last_time) & (ChatSession.id < last_id)))
        rows = self.db.execute(stmt.order_by(ordering_time.desc(), ChatSession.id.desc()).limit(limit + 1)).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        data = [
            {
                "id": row[0].id,
                "title": row[0].title,
                "created_at": row[0].created_at,
                "updated_at": row[0].updated_at,
                "last_message_at": row[0].last_message_at,
                "message_count": int(row[2] or 0),
                "last_message_preview": (row[3][:160] if row[3] else None),
            }
            for row in rows
        ]
        next_cursor = None
        if has_more and rows:
            raw = json.dumps({"time": rows[-1][1].isoformat(), "id": str(rows[-1][0].id)}, separators=(",", ":"))
            next_cursor = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
        return data, next_cursor

    def rename_session(self, session_id: uuid.UUID, title: str) -> ChatSession:
        clean = re.sub(r"\s+", " ", title).strip()
        if not clean or len(clean) > settings.CHAT_SESSION_TITLE_MAX_LENGTH:
            raise ChatError(400, "INVALID_TITLE", "Session title is invalid")
        session = self.get_session(session_id)
        session.title = clean
        session.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session_id: uuid.UUID) -> None:
        try:
            session = self.db.execute(select(ChatSession).where(*self._owned_session_predicate(session_id)).with_for_update()).scalar_one_or_none()
            if session is None:
                self.db.rollback()
                raise self._not_found()
            self._recover_stale_locked(session.id)
            active = self.db.execute(
                select(ChatTurn.id).where(ChatTurn.session_id == session.id, ChatTurn.state.in_(ACTIVE_STATES))
            ).scalar_one_or_none()
            if active:
                self.db.rollback()
                raise ChatError(409, "SESSION_BUSY", "Session has an active generation", turn_id=str(active))
            self.db.delete(session)
            self.db.commit()
        except ChatError:
            raise
        except Exception:
            self.db.rollback()
            raise

    def begin_turn(self, session_id: uuid.UUID, request: ChatTurnRequest) -> TurnHandle:
        request_hash = canonical_request_hash(request)
        try:
            session = self.db.execute(
                select(ChatSession).where(*self._owned_session_predicate(session_id)).with_for_update()
            ).scalar_one_or_none()
            if session is None:
                self.db.rollback()
                raise self._not_found()
            self._recover_stale_locked(session.id)
            existing = self.db.execute(
                select(ChatTurn).where(ChatTurn.session_id == session.id, ChatTurn.client_turn_id == request.client_turn_id)
            ).scalar_one_or_none()
            if existing:
                return self._resolve_existing(existing, request_hash, commit=True)
            active = self.db.execute(
                select(ChatTurn).where(ChatTurn.session_id == session.id, ChatTurn.state.in_(ACTIVE_STATES))
            ).scalar_one_or_none()
            if active:
                self.db.rollback()
                raise ChatError(
                    409,
                    "SESSION_TURN_IN_PROGRESS",
                    "Session already has an active turn",
                    turn_id=str(active.id),
                    state=active.state,
                )

            now = utcnow()
            scope = self._document_scope(request.document_ids)
            next_sequence = self.db.execute(
                select(func.coalesce(func.max(ChatMessage.sequence_no), 0)).where(ChatMessage.session_id == session.id)
            ).scalar_one()
            turn = ChatTurn(
                session_id=session.id,
                client_turn_id=request.client_turn_id,
                request_hash=request_hash,
                state=TurnState.PENDING.value,
                document_scope_json=scope,
                created_at=now,
                started_at=now,
            )
            user = ChatMessage(
                session_id=session.id,
                turn=turn,
                role=MessageRole.USER.value,
                sequence_no=next_sequence + 1,
                content=request.query.strip(),
                delivery_state=DeliveryState.COMMITTED.value,
                generation_metadata_json={},
                created_at=now,
            )
            assistant = ChatMessage(
                session_id=session.id,
                turn=turn,
                role=MessageRole.ASSISTANT.value,
                sequence_no=next_sequence + 2,
                content="",
                delivery_state=DeliveryState.STREAMING.value,
                generation_metadata_json={},
                created_at=now,
            )
            self.db.add_all([turn, user, assistant])
            self.db.flush()
            turn.state = TurnState.STREAMING.value
            if session.title == "New conversation" and next_sequence == 0:
                session.title = derive_title(request.query)
            session.updated_at = now
            session.last_message_at = now
            self.db.commit()
            return TurnHandle(turn.id, user.id, assistant.id, request_hash)
        except IntegrityError as exc:
            constraint = getattr(getattr(exc, "orig", None), "diag", None)
            constraint_name = getattr(constraint, "constraint_name", None)
            self.db.rollback()
            if constraint_name == "uq_chat_turn_session_client":
                existing = self.db.execute(
                    select(ChatTurn).where(ChatTurn.session_id == session_id, ChatTurn.client_turn_id == request.client_turn_id)
                ).scalar_one()
                return self._resolve_existing(existing, request_hash, commit=False)
            if constraint_name == "uq_chat_turn_one_active_per_session":
                active = self.db.execute(
                    select(ChatTurn).where(ChatTurn.session_id == session_id, ChatTurn.state.in_(ACTIVE_STATES))
                ).scalar_one_or_none()
                raise ChatError(
                    409,
                    "SESSION_TURN_IN_PROGRESS",
                    "Session already has an active turn",
                    turn_id=str(active.id) if active else None,
                    state=active.state if active else None,
                ) from exc
            raise
        except ChatError:
            raise
        except Exception:
            self.db.rollback()
            raise

    def _resolve_existing(self, turn: ChatTurn, request_hash: str, *, commit: bool) -> TurnHandle:
        if turn.request_hash != request_hash:
            self.db.rollback()
            raise ChatError(409, "IDEMPOTENCY_KEY_CONFLICT", "client_turn_id was already used with a different request")
        messages = self.db.execute(
            select(ChatMessage).where(ChatMessage.turn_id == turn.id).order_by(ChatMessage.sequence_no)
        ).scalars().all()
        user = next(item for item in messages if item.role == MessageRole.USER.value)
        assistant = next(item for item in messages if item.role == MessageRole.ASSISTANT.value)
        if commit:
            self.db.commit()
        if turn.state == TurnState.COMPLETED.value:
            return TurnHandle(turn.id, user.id, assistant.id, request_hash, replayed=True)
        if turn.state in ACTIVE_STATES:
            raise ChatError(
                409, "TURN_IN_PROGRESS", "This turn is still in progress", turn_id=str(turn.id), state=turn.state,
                assistant_message_id=str(assistant.id)
            )
        code = "TURN_FAILED" if turn.state == TurnState.FAILED.value else "TURN_CANCELLED"
        raise ChatError(409, code, "This logical turn is terminal; retry with a new client_turn_id", turn_id=str(turn.id), state=turn.state)

    def _document_scope(self, document_ids: list[uuid.UUID] | None) -> list[dict[str, Any]] | None:
        if not document_ids:
            return None
        documents = self.db.execute(select(Document).where(Document.id.in_(document_ids))).scalars().all()
        by_id = {item.id: item for item in documents}
        return [
            {
                "document_id": str(document_id),
                "document_sha256": by_id[document_id].sha256 if document_id in by_id else None,
                "filename": by_id[document_id].filename if document_id in by_id else None,
                "title": None,
            }
            for document_id in document_ids
        ]

    def _recover_stale_locked(self, session_id: uuid.UUID) -> bool:
        active = self.db.execute(
            select(ChatTurn).where(ChatTurn.session_id == session_id, ChatTurn.state.in_(ACTIVE_STATES)).with_for_update()
        ).scalar_one_or_none()
        if active is None:
            return False
        activity = active.started_at if active.state == TurnState.STREAMING.value else active.created_at
        cutoff = utcnow() - timedelta(seconds=settings.CHAT_TURN_STALE_AFTER_SECONDS)
        if activity is None or activity >= cutoff:
            return False
        now = utcnow()
        active.state = TurnState.FAILED.value
        active.completed_at = now
        active.failure_code = "ORPHANED_STREAM_TIMEOUT"
        active.failure_detail_safe = INTERRUPTED_MESSAGE
        assistant = self.db.execute(
            select(ChatMessage).where(ChatMessage.turn_id == active.id, ChatMessage.role == MessageRole.ASSISTANT.value).with_for_update()
        ).scalar_one()
        if assistant.delivery_state == DeliveryState.STREAMING.value:
            assistant.delivery_state = DeliveryState.FAILED.value
            assistant.answer_status = None
            assistant.finalized_at = now
        return True

    def load_messages(self, session_id: uuid.UUID, limit: int, before_sequence: int | None) -> tuple[list[ChatMessage], int | None, dict[uuid.UUID, dict[str, Any]]]:
        self.get_session(session_id)
        limit = min(max(limit, 1), settings.CHAT_MESSAGE_PAGE_SIZE_MAX)
        stmt = (
            select(ChatMessage)
            .options(selectinload(ChatMessage.citation_snapshots), selectinload(ChatMessage.turn))
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.sequence_no.desc())
            .limit(limit + 1)
        )
        if before_sequence is not None:
            stmt = stmt.where(ChatMessage.sequence_no < before_sequence)
        rows = self.db.execute(stmt).scalars().all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        rows.reverse()
        next_before = rows[0].sequence_no if has_more and rows else None
        snapshots = [snapshot for message in rows for snapshot in message.citation_snapshots]
        availability = self.resolve_availability(snapshots)
        return rows, next_before, availability

    def resolve_availability(self, snapshots: list[MessageCitationSnapshot]) -> dict[uuid.UUID, dict[str, Any]]:
        result = {item.id: {"availability": "SOURCE_UNAVAILABLE"} for item in snapshots}
        if not snapshots:
            return result
        try:
            original_ids = {item.original_document_id for item in snapshots if item.original_document_id}
            hashes = {item.document_sha256 for item in snapshots if item.document_sha256}
            documents = self.db.execute(
                select(Document).where(or_(Document.id.in_(original_ids), Document.sha256.in_(hashes)))
                .where(
                    DocumentAccessService.predicate(self.owner_user_id, Document.id)
                    if self.owner_user_id is not None else True
                )
            ).scalars().all()
            docs_by_id = {item.id: item for item in documents}
            docs_by_sha = {item.sha256: item for item in documents}
            candidate_doc_ids = {item.id for item in documents}
            chunks = self.db.execute(select(Chunk).where(Chunk.document_id.in_(candidate_doc_ids))).scalars().all()
            chunk_by_doc_hash = {(item.document_id, content_sha256(item.content_text)): item for item in chunks}
            for snapshot in snapshots:
                current_doc = docs_by_sha.get(snapshot.document_sha256) if snapshot.document_sha256 else None
                equivalent_chunk = chunk_by_doc_hash.get((current_doc.id, snapshot.chunk_content_sha256)) if current_doc else None
                if current_doc and equivalent_chunk:
                    result[snapshot.id] = {
                        "availability": "CURRENT_EQUIVALENT",
                        "current_document_id": current_doc.id,
                        "current_chunk_id": equivalent_chunk.id,
                    }
                elif snapshot.original_document_id in docs_by_id and snapshot.document_sha256 and docs_by_id[snapshot.original_document_id].sha256 != snapshot.document_sha256:
                    result[snapshot.id] = {
                        "availability": "SOURCE_UPDATED",
                        "current_document_id": snapshot.original_document_id,
                    }
        except Exception:
            self.db.rollback()
        return result

    def finalize_turn(
        self,
        handle: TurnHandle,
        result: GenerationResult,
        package: ContextPackage,
        request_id: str,
        timings: dict[str, float] | None = None,
    ) -> None:
        try:
            turn = self.db.execute(select(ChatTurn).where(ChatTurn.id == handle.turn_id).with_for_update()).scalar_one()
            assistant = self.db.execute(
                select(ChatMessage).where(ChatMessage.id == handle.assistant_message_id).with_for_update()
            ).scalar_one()
            if turn.state != TurnState.STREAMING.value or assistant.delivery_state != DeliveryState.STREAMING.value:
                raise ChatError(409, "TURN_NOT_ACTIVE", "Turn is no longer active")
            if assistant.role != MessageRole.ASSISTANT.value:
                raise ValueError("citation snapshots may only belong to an assistant message")
            selected = {item.source_id: item for item in package.selected_evidence}
            if result.status == GenerationStatus.INSUFFICIENT_EVIDENCE and result.citations:
                raise ValueError("insufficient-evidence completion cannot contain citations")
            cited_evidence = [selected[item.source_id] for item in result.citations if item.source_id in selected]
            if len(cited_evidence) != len(result.citations):
                raise ValueError("validated citation is missing selected evidence")
            document_ids = {uuid.UUID(item.document_id) for item in cited_evidence}
            documents = self.db.execute(select(Document).where(Document.id.in_(document_ids))).scalars().all() if document_ids else []
            docs = {str(item.id): item for item in documents}
            for order, evidence in enumerate(cited_evidence, 1):
                self.db.add(self._snapshot(assistant.id, evidence, order, docs.get(evidence.document_id)))

            now = utcnow()
            assistant.content = result.answer_text
            assistant.delivery_state = DeliveryState.COMPLETED.value
            assistant.answer_status = result.answerability_status.value if result.answerability_status else None
            assistant.model_id = result.model_id
            assistant.prompt_version = result.prompt_version
            assistant.prompt_hash = hashlib.sha256(load_system_prompt(result.prompt_version).encode("utf-8")).hexdigest()
            assistant.index_version = CANONICAL_INDEX_VERSION
            assistant.context_fingerprint = context_fingerprint(package, result.model_id, result.prompt_version)
            assistant.input_tokens = result.usage.input_tokens if result.usage else None
            assistant.output_tokens = result.usage.output_tokens if result.usage else None
            generation_ms = (timings or {}).get("generation_ms")
            assistant.generation_latency_ms = round(generation_ms) if generation_ms is not None else None
            assistant.generation_metadata_json = {
                "answerability_validation": result.answerability_validation.value,
                "citation_validation": result.citation_validation.value,
                "finish_reason": result.finish_reason,
                "generation_status": result.status.value,
                "request_id": request_id,
                "timings_ms": {key: round(value, 3) for key, value in (timings or {}).items()},
            }
            assistant.finalized_at = now
            turn.state = TurnState.COMPLETED.value
            turn.completed_at = now
            session = self.db.execute(select(ChatSession).where(ChatSession.id == turn.session_id).with_for_update()).scalar_one()
            session.updated_at = now
            session.last_message_at = now
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _snapshot(self, message_id: uuid.UUID, evidence: SelectedEvidence, order: int, document: Document | None) -> MessageCitationSnapshot:
        metadata = dict(evidence.metadata_json or {})
        provenance = dict(evidence.provenance_json or {})
        def first(*keys: str):
            for key in keys:
                value = metadata.get(key, provenance.get(key))
                if value is not None:
                    return value
            return None
        def as_text(value):
            return None if value is None else str(value)
        def as_int(value):
            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                return None
        return MessageCitationSnapshot(
            message_id=message_id,
            citation_label=evidence.source_id,
            citation_order=order,
            original_document_id=uuid.UUID(evidence.document_id) if evidence.document_id else None,
            original_chunk_id=uuid.UUID(evidence.chunk_id) if evidence.chunk_id else None,
            original_legal_unit_id=uuid.UUID(evidence.legal_unit_id) if evidence.legal_unit_id else None,
            document_title=as_text(first("document_title", "title")),
            document_filename=document.filename if document else as_text(first("filename", "document_filename")),
            document_sha256=document.sha256 if document else as_text(first("document_sha256", "sha256")),
            chunk_content_sha256=content_sha256(evidence.content_text),
            page_start=as_int(first("page_start")),
            page_end=as_int(first("page_end")),
            article=as_text(first("article", "article_number")),
            clause=as_text(first("clause", "clause_number")),
            point=as_text(first("point", "point_number")),
            evidence_text=evidence.content_text,
            metadata_json=metadata,
            provenance_json=provenance,
            snapshot_version=1,
        )

    def mark_terminal(self, handle: TurnHandle, state: TurnState, code: str, safe_detail: str, partial_content: str = "") -> None:
        if state not in (TurnState.FAILED, TurnState.CANCELLED):
            raise ValueError("terminal failure state required")
        self.db.rollback()
        try:
            turn = self.db.execute(select(ChatTurn).where(ChatTurn.id == handle.turn_id).with_for_update()).scalar_one_or_none()
            if turn is None or turn.state not in ACTIVE_STATES:
                self.db.rollback()
                return
            now = utcnow()
            turn.state = state.value
            turn.completed_at = now
            turn.failure_code = code
            turn.failure_detail_safe = safe_detail
            assistant = self.db.execute(select(ChatMessage).where(ChatMessage.id == handle.assistant_message_id).with_for_update()).scalar_one()
            assistant.delivery_state = DeliveryState.FAILED.value if state == TurnState.FAILED else DeliveryState.CANCELLED.value
            assistant.answer_status = None
            if partial_content:
                assistant.content = partial_content
            assistant.finalized_at = now
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def replay_payload(self, handle: TurnHandle) -> dict[str, Any]:
        assistant = self.db.execute(
            select(ChatMessage).options(selectinload(ChatMessage.citation_snapshots)).where(ChatMessage.id == handle.assistant_message_id)
        ).scalar_one()
        metadata = assistant.generation_metadata_json or {}
        return {
            "request_id": metadata.get("request_id", str(handle.turn_id)),
            "status": metadata.get("generation_status", "INSUFFICIENT_EVIDENCE" if assistant.answer_status == "INSUFFICIENT_EVIDENCE" else "COMPLETED"),
            "answer_text": assistant.content,
            "citations": [
                {
                    "source_id": item.citation_label,
                    "chunk_id": str(item.original_chunk_id) if item.original_chunk_id else "",
                    "document_id": str(item.original_document_id) if item.original_document_id else "",
                    "metadata_json": item.metadata_json,
                    "provenance_json": item.provenance_json,
                }
                for item in assistant.citation_snapshots
            ],
            "invalid_citations": [],
            "citation_validation": metadata.get("citation_validation", "PASS"),
            "model_id": assistant.model_id,
            "prompt_version": assistant.prompt_version,
            "finish_reason": metadata.get("finish_reason"),
            "usage": {"input_tokens": assistant.input_tokens, "output_tokens": assistant.output_tokens},
            "answerability_status": assistant.answer_status,
            "answerability_validation": metadata.get("answerability_validation", "NOT_APPLICABLE"),
        }

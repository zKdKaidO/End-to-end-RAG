from sqlalchemy import event, text

from app.context.schemas import StopReason
from app.context.service import ContextBuilderService
from app.db.database import SessionLocal, engine
from app.retrieval.schemas import RetrievalRequest
from app.retrieval.service import RetrievalService, validate_request
from tests.context_doubles import CharacterTokenCounter


def test_canonical_block4_to_block5_without_block5_database_queries():
    statements = []

    def record_statement(*args):
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", record_statement)
    db = SessionLocal()
    try:
        document_id = db.execute(
            text(
                """
                SELECT id FROM documents
                WHERE filename = 'sample_legal.pdf'
                ORDER BY created_at
                LIMIT 1
                """
            )
        ).scalar_one()
        params = validate_request(
            RetrievalRequest(
                query_text="bảo hiểm hưu trí bổ sung người lao động",
                top_k_dense=10,
                top_k_lexical=10,
                top_k_final=8,
                document_ids=[str(document_id)],
            )
        )
        retrieved = RetrievalService(db).retrieve(params)
        assert retrieved

        statements.clear()
        package = ContextBuilderService(CharacterTokenCounter()).build(
            request_id="block5-canonical-integration",
            query_text=params.query_text,
            retrieved_candidates=retrieved,
            context_budget_tokens=2_500,
        )

        assert statements == []
        assert package.candidate_count == len(retrieved)
        assert package.selected_count > 0
        assert [item.source_id for item in package.selected_evidence] == [
            f"S{index}" for index in range(1, package.selected_count + 1)
        ]
        assert [item.retrieval_final_rank for item in package.selected_evidence] == sorted(
            item.retrieval_final_rank for item in package.selected_evidence
        )
        assert package.context_token_count == len(package.context_text)
        assert package.context_token_count <= package.context_budget_tokens
        assert package.stop_reason in {StopReason.NONE, StopReason.TOKEN_BUDGET}
    finally:
        db.close()
        event.remove(engine, "before_cursor_execute", record_statement)

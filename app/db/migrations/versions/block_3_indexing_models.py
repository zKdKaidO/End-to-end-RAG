"""Add indexing models

Revision ID: block_3_indexing_models
Revises: c9c22b5f4ee4
Create Date: 2026-08-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector

# revision identifiers, used by Alembic.
revision = 'block_3_indexing_models'
down_revision = 'c9c22b5f4ee4'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create indexing_jobs table
    op.create_table('indexing_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('current_stage', sa.String(), nullable=False),
        sa.Column('chunks_total', sa.Integer(), nullable=True),
        sa.Column('chunks_indexed', sa.Integer(), nullable=True),
        sa.Column('embedding_model', sa.String(), nullable=True),
        sa.Column('index_version', sa.String(), nullable=True),
        sa.Column('error_stage', sa.String(), nullable=True),
        sa.Column('error_type', sa.String(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create chunk_indexes table
    op.create_table('chunk_indexes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('chunk_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
        sa.Column('lexical_tsv', postgresql.TSVECTOR(), nullable=True),
        sa.Column('embedding_model', sa.String(), nullable=False),
        sa.Column('embedding_dimension', sa.Integer(), nullable=False),
        sa.Column('index_version', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['chunk_id'], ['chunks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chunk_id')
    )
    
    op.create_index('ix_chunk_indexes_document_id', 'chunk_indexes', ['document_id'], unique=False)
    op.create_index('ix_chunk_indexes_embedding', 'chunk_indexes', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_chunk_indexes_lexical_tsv', 'chunk_indexes', ['lexical_tsv'], unique=False, postgresql_using='gin')


def downgrade() -> None:
    op.drop_index('ix_chunk_indexes_lexical_tsv', table_name='chunk_indexes')
    op.drop_index('ix_chunk_indexes_embedding', table_name='chunk_indexes')
    op.drop_index('ix_chunk_indexes_document_id', table_name='chunk_indexes')
    op.drop_table('chunk_indexes')
    op.drop_table('indexing_jobs')

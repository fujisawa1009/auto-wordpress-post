"""Initial database tables

Revision ID: 001_initial_tables
Revises:
Create Date: 2025-09-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create articles table
    op.create_table('articles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('input_payload', sa.JSON(), nullable=False),
        sa.Column('output_payload', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'GENERATING', 'GENERATED', 'PUBLISHING', 'PUBLISHED', 'FAILED', name='articlestatus'), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=True),
        sa.Column('char_count', sa.Integer(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=64), nullable=True),
        sa.Column('wp_post_id', sa.Integer(), nullable=True),
        sa.Column('wp_url', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_articles_idempotency_key'), 'articles', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_articles_slug'), 'articles', ['slug'], unique=True)
    op.create_index(op.f('ix_articles_status'), 'articles', ['status'], unique=False)

    # Create jobs table
    op.create_table('jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.Enum('GENERATE', 'PUBLISH', 'MEDIA_UPLOAD', name='jobtype'), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', name='jobstatus'), nullable=False),
        sa.Column('tries', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'], unique=False)
    op.create_index(op.f('ix_jobs_type'), 'jobs', ['type'], unique=False)

    # Create taxonomies table
    op.create_table('taxonomies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type', sa.Enum('CATEGORY', 'TAG', name='taxonomytype'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('wp_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('type', 'name', name='unique_type_name'),
        sa.UniqueConstraint('type', 'slug', name='unique_type_slug'),
        sa.UniqueConstraint('wp_id', name='taxonomies_wp_id_key')
    )
    op.create_index(op.f('ix_taxonomies_type_name'), 'taxonomies', ['type', 'name'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_taxonomies_type_name'), table_name='taxonomies')
    op.drop_table('taxonomies')
    op.drop_index(op.f('ix_jobs_type'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_status'), table_name='jobs')
    op.drop_table('jobs')
    op.drop_index(op.f('ix_articles_status'), table_name='articles')
    op.drop_index(op.f('ix_articles_slug'), table_name='articles')
    op.drop_index(op.f('ix_articles_idempotency_key'), table_name='articles')
    op.drop_table('articles')

    # Drop enums
    sa.Enum('CATEGORY', 'TAG', name='taxonomytype').drop(op.get_bind())
    sa.Enum('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', name='jobstatus').drop(op.get_bind())
    sa.Enum('GENERATE', 'PUBLISH', 'MEDIA_UPLOAD', name='jobtype').drop(op.get_bind())
    sa.Enum('PENDING', 'GENERATING', 'GENERATED', 'PUBLISHING', 'PUBLISHED', 'FAILED', name='articlestatus').drop(op.get_bind())
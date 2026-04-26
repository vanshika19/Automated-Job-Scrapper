"""initial schema (companies, jobs, job_embeddings).

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-26
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("name", sa.String(), primary_key=True),
        sa.Column("careers_url", sa.Text()),
        sa.Column("linkedin_url", sa.Text()),
        sa.Column("country", sa.Text()),
        sa.Column("segment", sa.Text()),
    )

    op.create_table(
        "jobs",
        sa.Column("fingerprint", sa.String(length=64), primary_key=True),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("location", sa.Text()),
        sa.Column("department", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("source", sa.Text()),
        sa.Column("posted_at", sa.Text()),
        sa.Column("scraped_at", sa.Text()),
        sa.Column("last_seen_at", sa.Text()),
        sa.Column("status", sa.Text(), server_default="open"),
    )
    op.create_index("idx_jobs_company", "jobs", ["company"])
    op.create_index("idx_jobs_source", "jobs", ["source"])
    op.create_index("idx_jobs_status", "jobs", ["status"])

    op.create_table(
        "job_embeddings",
        sa.Column("fingerprint", sa.String(length=64), primary_key=True),
        sa.Column("embedder", sa.String(length=128), primary_key=True),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("vector", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("job_embeddings")
    op.drop_index("idx_jobs_status", table_name="jobs")
    op.drop_index("idx_jobs_source", table_name="jobs")
    op.drop_index("idx_jobs_company", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("companies")
